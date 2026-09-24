"""
app.py - Main HTTP/REST API Server for Shree Sagarmatha Secondary School & Sagarmatha EMS
Includes Multi-Tier Role-Based Access Control (RBAC), Authentication, and Nepal CDC Grading.
Zero external dependencies, running on Python 3 built-in http.server and sqlite3.
"""

import http.server
import socketserver
import json
import urllib.parse
import os
import mimetypes
from datetime import datetime
from database import (
    init_db,
    get_db_connection,
    calculate_subject_evaluation,
    calculate_grade_and_gp,
    authenticate_user,
    create_session,
    validate_session,
    delete_session,
    create_user,
    change_user_password
)

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 8000))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

class EMSRequestHandler(http.server.BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        pass

    def send_json(self, data, status_code=200):
        body = json.dumps(data, default=str).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def parse_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            raw_data = self.rfile.read(content_length).decode('utf-8')
            try:
                return json.loads(raw_data)
            except Exception:
                return urllib.parse.parse_qs(raw_data)
        return {}

    def get_auth_token(self, query=None):
        # 1. Authorization header: Bearer <token>
        auth_header = self.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            return auth_header.split(' ', 1)[1].strip()
        
        # 2. Query param ?token=...
        if query and 'token' in query:
            return query['token'][0]

        # 3. Cookie: session_token=...
        cookie_header = self.headers.get('Cookie', '')
        if 'session_token=' in cookie_header:
            for part in cookie_header.split(';'):
                part = part.strip()
                if part.startswith('session_token='):
                    return part.split('=', 1)[1].strip()

        return None

    def get_current_user(self, query=None):
        token = self.get_auth_token(query)
        if not token:
            return None
        return validate_session(token)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        def q(key, default=None):
            return query.get(key, [default])[0]

        # API Routes
        if path.startswith("/api/"):
            try:
                self.handle_api_get(path, query, q)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_json({"error": str(e)}, 500)
            return

        # Static File Serving
        if path.startswith("/static/"):
            rel_path = path[len("/static/"):]
            file_path = os.path.join(STATIC_DIR, rel_path)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                self.serve_file(file_path)
                return
            else:
                self.send_error(404, "Static file not found")
                return

        # Default: Serve SPA index.html
        index_file = os.path.join(TEMPLATES_DIR, "index.html")
        if os.path.exists(index_file):
            self.serve_file(index_file, "text/html; charset=utf-8")
        else:
            self.send_error(404, "Index template not found")

    def serve_file(self, filepath, content_type=None):
        if not content_type:
            content_type, _ = mimetypes.guess_type(filepath)
            if not content_type:
                content_type = "application/octet-stream"
        
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Error reading file: {str(e)}")

    def handle_api_get(self, path, query, q):
        # 1. Completely Public Endpoints (Accessible without login)
        conn = get_db_connection()
        cur = conn.cursor()

        if path == "/api/info":
            cur.execute("SELECT * FROM school_info WHERE id = 1;")
            info = dict(cur.fetchone() or {})
            
            cur.execute("SELECT COUNT(*) AS count FROM students WHERE status = 'Active';")
            active_students = cur.fetchone()['count']

            cur.execute("SELECT COUNT(*) AS count FROM staff WHERE status = 'Active';")
            active_staff = cur.fetchone()['count']

            cur.execute("SELECT COUNT(*) AS count FROM classes;")
            total_classes = cur.fetchone()['count']

            cur.execute("SELECT IFNULL(SUM(amount_paid), 0) AS total_collected FROM payments;")
            total_fee_collected = cur.fetchone()['total_collected']

            cur.execute("SELECT IFNULL(SUM(total_amount - paid_amount - discount), 0) AS total_due FROM invoices WHERE status != 'Paid';")
            total_fee_due = cur.fetchone()['total_due']

            cur.execute("SELECT IFNULL(SUM(amount), 0) AS total_expense FROM expenses;")
            total_expense = cur.fetchone()['total_expense']

            info['stats'] = {
                "active_students": active_students,
                "active_staff": active_staff,
                "total_classes": total_classes,
                "total_fee_collected": total_fee_collected,
                "total_fee_due": max(0, total_fee_due),
                "total_expense": total_expense,
                "established_bs": info.get('established_bs', 2034)
            }
            conn.close()
            self.send_json(info)
            return

        if path == "/api/notices":
            category = q('category')
            if category and category != 'All':
                cur.execute("SELECT * FROM notices WHERE category = ? ORDER BY is_pinned DESC, posted_date DESC;", (category,))
            else:
                cur.execute("SELECT * FROM notices ORDER BY is_pinned DESC, posted_date DESC;")
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            self.send_json(rows)
            return

        # Public Curriculum & Academic Structure Endpoints
        if path == "/api/classes":
            cur.execute("""
            SELECT c.*, 
                   COUNT(DISTINCT s.id) AS student_count,
                   GROUP_CONCAT(DISTINCT sec.name) AS sections
            FROM classes c
            LEFT JOIN students s ON s.class_id = c.id AND s.status = 'Active'
            LEFT JOIN sections sec ON sec.class_id = c.id
            GROUP BY c.id
            ORDER BY c.numeric_level ASC;
            """)
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            self.send_json(rows)
            return

        if path == "/api/sections":
            cid = q('class_id')
            if cid:
                cur.execute("SELECT * FROM sections WHERE class_id = ? ORDER BY name ASC;", (cid,))
            else:
                cur.execute("SELECT * FROM sections ORDER BY class_id, name ASC;")
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            self.send_json(rows)
            return

        if path == "/api/subjects":
            cid = q('class_id')
            if cid:
                cur.execute("SELECT * FROM subjects WHERE class_id = ? ORDER BY id ASC;", (cid,))
            else:
                cur.execute("SELECT sub.*, c.name AS class_name FROM subjects sub JOIN classes c ON sub.class_id = c.id ORDER BY c.numeric_level, sub.id ASC;")
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            self.send_json(rows)
            return

        if path == "/api/exams":
            cur.execute("SELECT * FROM exams ORDER BY id DESC;")
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            self.send_json(rows)
            return

        if path == "/api/gallery":
            category = q('category')
            if category and category != 'All':
                cur.execute("SELECT * FROM gallery_photos WHERE category = ? ORDER BY sort_order ASC, id ASC;", (category,))
            else:
                cur.execute("SELECT * FROM gallery_photos ORDER BY sort_order ASC, id ASC;")
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            self.send_json(rows)
            return

        # 2. Authentication Check for All Protected EMS Endpoints
        user = self.get_current_user(query)

        if path == "/api/auth/me":
            conn.close()
            if not user:
                self.send_json({"authenticated": False}, 401)
            else:
                self.send_json({
                    "authenticated": True,
                    "user": {
                        "id": user['user_id'],
                        "username": user['username'],
                        "full_name": user['full_name'],
                        "role": user['role'],
                        "linked_student_id": user['linked_student_id'],
                        "linked_staff_id": user['linked_staff_id']
                    }
                })
            return

        if not user:
            conn.close()
            self.send_json({"error": "Authentication required. Please log in to Sagarmatha EMS."}, 401)
            return

        role = user['role']
        student_id_override = user['linked_student_id'] if role == 'student' else None

        # 3. Role-Based Access Guards
        # 3a. Finance endpoints: Forbidden for Teacher and Student
        if path.startswith("/api/finance/") and role == "teacher":
            conn.close()
            self.send_json({"error": "Access denied. Teachers cannot access School Finance."}, 403)
            return

        if path in ["/api/finance/summary", "/api/finance/structure", "/api/finance/heads", "/api/finance/expenses"] and role == "student":
            conn.close()
            self.send_json({"error": "Access denied. School finance records are restricted."}, 403)
            return

        # 3b. Tabulation Ledger: Forbidden for Student
        if path == "/api/tabulation" and role == "student":
            conn.close()
            self.send_json({"error": "Access denied. Class Tabulation Ledger is restricted to faculty."}, 403)
            return

        # 4. Students List & Details
        if path == "/api/students":
            if role == "student":
                # A student can only view their own record
                cur.execute("""
                SELECT s.*, c.name AS class_name, sec.name AS section_name
                FROM students s
                JOIN classes c ON s.class_id = c.id
                JOIN sections sec ON s.section_id = sec.id
                WHERE s.id = ?;
                """, (student_id_override,))
                rows = [dict(r) for r in cur.fetchall()]
                conn.close()
                self.send_json(rows)
                return

            cid = q('class_id')
            sec_id = q('section_id')
            search = q('search')
            status = q('status', 'Active')

            sql = """
            SELECT s.*, c.name AS class_name, sec.name AS section_name
            FROM students s
            JOIN classes c ON s.class_id = c.id
            JOIN sections sec ON s.section_id = sec.id
            WHERE 1=1
            """
            params = []
            if cid:
                sql += " AND s.class_id = ?"
                params.append(cid)
            if sec_id:
                sql += " AND s.section_id = ?"
                params.append(sec_id)
            if status and status != 'All':
                sql += " AND s.status = ?"
                params.append(status)
            if search:
                sql += " AND (s.first_name LIKE ? OR s.last_name LIKE ? OR s.reg_no LIKE ? OR s.guardian_phone LIKE ?)"
                term = f"%{search}%"
                params.extend([term, term, term, term])
            
            sql += " ORDER BY c.numeric_level ASC, sec.name ASC, s.roll_no ASC;"
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            self.send_json(rows)
            return

        if path.startswith("/api/students/"):
            student_id = path.split("/")[-1]
            if role == "student" and str(student_id) != str(student_id_override):
                conn.close()
                self.send_json({"error": "Access denied. You can only view your own student profile."}, 403)
                return

            cur.execute("""
            SELECT s.*, c.name AS class_name, sec.name AS section_name
            FROM students s
            JOIN classes c ON s.class_id = c.id
            JOIN sections sec ON s.section_id = sec.id
            WHERE s.id = ?;
            """, (student_id,))
            student = cur.fetchone()
            if not student:
                conn.close()
                self.send_json({"error": "Student not found"}, 404)
                return
            
            res = dict(student)
            
            cur.execute("""
            SELECT * FROM invoices WHERE student_id = ? ORDER BY id DESC LIMIT 5;
            """, (student_id,))
            res['invoices'] = [dict(r) for r in cur.fetchall()]

            cur.execute("""
            SELECT status, COUNT(*) as count FROM attendance WHERE student_id = ? GROUP BY status;
            """, (student_id,))
            res['attendance_summary'] = {r['status']: r['count'] for r in cur.fetchall()}

            conn.close()
            self.send_json(res)
            return

        # 6. Marks Query
        if path == "/api/marks":
            if role == "student":
                conn.close()
                self.send_json({"error": "Access denied to bulk marks sheet."}, 403)
                return

            exam_id = q('exam_id')
            class_id = q('class_id')
            subject_id = q('subject_id')

            if not exam_id or not class_id or not subject_id:
                conn.close()
                self.send_json({"error": "exam_id, class_id, and subject_id are required"}, 400)
                return

            cur.execute("""
            SELECT s.id AS student_id, s.roll_no, s.first_name, s.last_name, s.name_np, s.reg_no, sec.name as section_name,
                   IFNULL(m.theory_obtained, 0) AS theory_obtained,
                   IFNULL(m.practical_obtained, 0) AS practical_obtained,
                   m.id AS mark_id
            FROM students s
            JOIN sections sec ON s.section_id = sec.id
            LEFT JOIN marks m ON m.student_id = s.id AND m.exam_id = ? AND m.subject_id = ?
            WHERE s.class_id = ? AND s.status = 'Active'
            ORDER BY sec.name ASC, s.roll_no ASC;
            """, (exam_id, subject_id, class_id))
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            self.send_json(rows)
            return

        # 9. Official Nepal CDC Grade Sheet Preparation
        if path == "/api/gradesheet":
            student_id = q('student_id')
            exam_id = q('exam_id')

            # Enforce self-only for student role
            if role == "student":
                student_id = student_id_override

            if not student_id or not exam_id:
                conn.close()
                self.send_json({"error": "student_id and exam_id are required"}, 400)
                return

            cur.execute("SELECT * FROM school_info WHERE id = 1;")
            school = dict(cur.fetchone() or {})

            cur.execute("""
            SELECT s.*, c.name AS class_name, c.numeric_level, sec.name AS section_name
            FROM students s
            JOIN classes c ON s.class_id = c.id
            JOIN sections sec ON s.section_id = sec.id
            WHERE s.id = ?;
            """, (student_id,))
            student = cur.fetchone()
            if not student:
                conn.close()
                self.send_json({"error": "Student not found"}, 404)
                return

            cur.execute("SELECT * FROM exams WHERE id = ?;", (exam_id,))
            exam = cur.fetchone()
            if not exam:
                conn.close()
                self.send_json({"error": "Exam not found"}, 404)
                return

            cur.execute("""
            SELECT sub.*, 
                   IFNULL(m.theory_obtained, 0) AS theory_obtained,
                   IFNULL(m.practical_obtained, 0) AS practical_obtained,
                   m.id as mark_id
            FROM subjects sub
            LEFT JOIN marks m ON m.subject_id = sub.id AND m.exam_id = ? AND m.student_id = ?
            WHERE sub.class_id = ?
            ORDER BY sub.id ASC;
            """, (exam_id, student_id, student['class_id']))
            subjects = cur.fetchall()

            evaluated_subjects = []
            total_credit_hours = 0.0
            total_weighted_gp = 0.0
            has_ng = False
            total_marks_obtained = 0.0
            total_full_marks = 0.0

            for sub in subjects:
                eval_data = calculate_subject_evaluation(
                    theory_obtained=sub['theory_obtained'],
                    theory_full=sub['theory_full_marks'],
                    practical_obtained=sub['practical_obtained'],
                    practical_full=sub['practical_full_marks'],
                    credit_hours=sub['credit_hours']
                )
                eval_data['code'] = sub['code']
                eval_data['name_en'] = sub['name_en']
                eval_data['name_np'] = sub['name_np']
                eval_data['is_optional'] = sub['is_optional']

                total_credit_hours += sub['credit_hours']
                total_weighted_gp += eval_data['weighted_gp']
                total_marks_obtained += eval_data['total_obtained']
                total_full_marks += eval_data['total_full']

                if eval_data['final_grade'] == 'NG':
                    has_ng = True

                evaluated_subjects.append(eval_data)

            gpa = round(total_weighted_gp / total_credit_hours, 2) if total_credit_hours > 0 else 0.0
            overall_pct = round((total_marks_obtained / total_full_marks * 100), 2) if total_full_marks > 0 else 0.0
            overall_grade, _, overall_desc = calculate_grade_and_gp(overall_pct)

            if has_ng:
                gpa_display = "NG"
                result_status = "Non-Graded (NG)"
                result_remarks = "Failed to secure minimum grade in one or more subjects. Eligible for grade increment examination."
            else:
                gpa_display = f"{gpa:.2f}"
                result_status = f"Graded ({overall_grade})"
                result_remarks = f"Promoted with {overall_desc} performance."

            response_data = {
                "school": school,
                "student": dict(student),
                "exam": dict(exam),
                "subjects": evaluated_subjects,
                "summary": {
                    "total_credit_hours": total_credit_hours,
                    "total_marks_obtained": total_marks_obtained,
                    "total_full_marks": total_full_marks,
                    "percentage": overall_pct,
                    "gpa": gpa,
                    "gpa_display": gpa_display,
                    "overall_grade": overall_grade if not has_ng else "NG",
                    "result_status": result_status,
                    "result_remarks": result_remarks,
                    "has_ng": has_ng,
                    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            }
            conn.close()
            self.send_json(response_data)
            return

        # 10. Class Tabulation Ledger
        if path == "/api/tabulation":
            exam_id = q('exam_id')
            class_id = q('class_id')

            if not exam_id or not class_id:
                conn.close()
                self.send_json({"error": "exam_id and class_id are required"}, 400)
                return

            cur.execute("SELECT * FROM classes WHERE id = ?;", (class_id,))
            class_row = cur.fetchone()

            cur.execute("SELECT * FROM exams WHERE id = ?;", (exam_id,))
            exam_row = cur.fetchone()

            cur.execute("SELECT * FROM subjects WHERE class_id = ? ORDER BY id ASC;", (class_id,))
            subjects = [dict(s) for s in cur.fetchall()]

            cur.execute("""
            SELECT s.*, sec.name AS section_name
            FROM students s
            JOIN sections sec ON s.section_id = sec.id
            WHERE s.class_id = ? AND s.status = 'Active'
            ORDER BY sec.name ASC, s.roll_no ASC;
            """, (class_id,))
            students = [dict(st) for st in cur.fetchall()]

            cur.execute("""
            SELECT student_id, subject_id, theory_obtained, practical_obtained
            FROM marks
            WHERE exam_id = ?;
            """, (exam_id,))
            marks_map = {}
            for m in cur.fetchall():
                marks_map[f"{m['student_id']}_{m['subject_id']}"] = m

            ledger_students = []
            for st in students:
                st_subs = []
                st_total_ch = 0.0
                st_total_wgp = 0.0
                st_has_ng = False
                st_total_marks = 0.0

                for sub in subjects:
                    m = marks_map.get(f"{st['id']}_{sub['id']}")
                    th = m['theory_obtained'] if m else 0.0
                    pr = m['practical_obtained'] if m else 0.0

                    eval_res = calculate_subject_evaluation(
                        theory_obtained=th,
                        theory_full=sub['theory_full_marks'],
                        practical_obtained=pr,
                        practical_full=sub['practical_full_marks'],
                        credit_hours=sub['credit_hours']
                    )

                    st_total_ch += sub['credit_hours']
                    st_total_wgp += eval_res['weighted_gp']
                    st_total_marks += eval_res['total_obtained']
                    if eval_res['final_grade'] == 'NG':
                        st_has_ng = True

                    st_subs.append({
                        "subject_id": sub['id'],
                        "code": sub['code'],
                        "theory": th,
                        "practical": pr,
                        "total": eval_res['total_obtained'],
                        "grade": eval_res['final_grade'],
                        "gp": eval_res['final_gp']
                    })

                gpa = round(st_total_wgp / st_total_ch, 2) if st_total_ch > 0 else 0.0
                ledger_students.append({
                    "id": st['id'],
                    "roll_no": st['roll_no'],
                    "name": f"{st['first_name']} {st['last_name']}",
                    "name_np": st['name_np'],
                    "reg_no": st['reg_no'],
                    "section": st['section_name'],
                    "subject_evals": st_subs,
                    "total_marks": st_total_marks,
                    "gpa": gpa if not st_has_ng else 0.0,
                    "gpa_display": f"{gpa:.2f}" if not st_has_ng else "NG",
                    "status": "PASS" if not st_has_ng else "NG"
                })

            sorted_by_gpa = sorted([s for s in ledger_students if s['status'] == 'PASS'], key=lambda x: x['gpa'], reverse=True)
            rank = 1
            for s in sorted_by_gpa:
                s['rank'] = rank
                rank += 1

            conn.close()
            self.send_json({
                "class": dict(class_row),
                "exam": dict(exam_row),
                "subjects": subjects,
                "students": ledger_students
            })
            return

        # 11. Finance Modules
        if path == "/api/finance/structure":
            cid = q('class_id')
            cur.execute("""
            SELECT fs.*, fh.name AS fee_head_name, fh.is_recurring, c.name AS class_name
            FROM fee_structures fs
            JOIN fee_heads fh ON fs.fee_head_id = fh.id
            JOIN classes c ON fs.class_id = c.id
            WHERE (? IS NULL OR fs.class_id = ?)
            ORDER BY c.numeric_level, fh.id;
            """, (cid, cid))
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            self.send_json(rows)
            return

        if path == "/api/finance/heads":
            cur.execute("SELECT * FROM fee_heads ORDER BY id ASC;")
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            self.send_json(rows)
            return

        if path == "/api/finance/invoices":
            st_id = q('student_id')
            if role == "student":
                st_id = student_id_override

            cid = q('class_id')
            status = q('status')

            sql = """
            SELECT inv.*, s.first_name, s.last_name, s.reg_no, s.roll_no, c.name AS class_name, sec.name AS section_name
            FROM invoices inv
            JOIN students s ON inv.student_id = s.id
            JOIN classes c ON s.class_id = c.id
            JOIN sections sec ON s.section_id = sec.id
            WHERE 1=1
            """
            params = []
            if st_id:
                sql += " AND inv.student_id = ?"
                params.append(st_id)
            if cid:
                sql += " AND s.class_id = ?"
                params.append(cid)
            if status and status != 'All':
                sql += " AND inv.status = ?"
                params.append(status)
            sql += " ORDER BY inv.id DESC LIMIT 100;"

            cur.execute(sql, params)
            invoices = [dict(r) for r in cur.fetchall()]
            conn.close()
            self.send_json(invoices)
            return

        if path.startswith("/api/finance/receipt/"):
            receipt_no = path.split("/")[-1]
            cur.execute("""
            SELECT p.*, inv.invoice_no, inv.month, inv.year, inv.total_amount, inv.discount, inv.fine, inv.paid_amount AS total_inv_paid,
                   s.first_name, s.last_name, s.name_np, s.reg_no, s.roll_no, s.guardian_name, s.guardian_phone,
                   c.name AS class_name, sec.name AS section_name
            FROM payments p
            JOIN invoices inv ON p.invoice_id = inv.id
            JOIN students s ON p.student_id = s.id
            JOIN classes c ON s.class_id = c.id
            JOIN sections sec ON s.section_id = sec.id
            WHERE p.receipt_no = ?;
            """, (receipt_no,))
            rec = cur.fetchone()
            if not rec:
                conn.close()
                self.send_json({"error": "Receipt not found"}, 404)
                return

            # Check if student is accessing their own receipt
            if role == "student" and str(rec['student_id']) != str(student_id_override):
                conn.close()
                self.send_json({"error": "Access denied to receipt"}, 403)
                return

            res = dict(rec)
            cur.execute("SELECT * FROM invoice_items WHERE invoice_id = ?;", (res['invoice_id'],))
            res['items'] = [dict(r) for r in cur.fetchall()]

            cur.execute("SELECT * FROM school_info WHERE id = 1;")
            res['school'] = dict(cur.fetchone() or {})

            due_remaining = max(0.0, res['total_amount'] + res['fine'] - res['discount'] - res['total_inv_paid'])
            res['due_remaining'] = due_remaining

            conn.close()
            self.send_json(res)
            return

        if path == "/api/finance/expenses":
            cur.execute("SELECT * FROM expenses ORDER BY expense_date DESC, id DESC LIMIT 100;")
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            self.send_json(rows)
            return

        if path == "/api/finance/summary":
            cur.execute("SELECT IFNULL(SUM(amount_paid), 0) AS total_collected FROM payments;")
            collected = cur.fetchone()['total_collected']

            cur.execute("SELECT IFNULL(SUM(total_amount + fine - discount - paid_amount), 0) AS total_due FROM invoices WHERE status != 'Paid';")
            dues = cur.fetchone()['total_due']

            cur.execute("SELECT IFNULL(SUM(amount), 0) AS total_expenses FROM expenses;")
            expenses = cur.fetchone()['total_expenses']

            cur.execute("""
            SELECT category, SUM(amount) as total
            FROM expenses
            GROUP BY category
            ORDER BY total DESC;
            """)
            expense_by_cat = [dict(r) for r in cur.fetchall()]

            cur.execute("""
            SELECT payment_mode, SUM(amount_paid) as total
            FROM payments
            GROUP BY payment_mode;
            """)
            payments_by_mode = [dict(r) for r in cur.fetchall()]

            cur.execute("""
            SELECT p.receipt_no, p.amount_paid, p.payment_mode, p.payment_date, s.first_name, s.last_name, c.name as class_name
            FROM payments p
            JOIN students s ON p.student_id = s.id
            JOIN classes c ON s.class_id = c.id
            ORDER BY p.id DESC LIMIT 10;
            """)
            recent_payments = [dict(r) for r in cur.fetchall()]

            conn.close()
            self.send_json({
                "total_collected": collected,
                "total_due": max(0, dues),
                "total_expenses": expenses,
                "net_cashflow": collected - expenses,
                "expense_by_category": expense_by_cat,
                "payments_by_mode": payments_by_mode,
                "recent_payments": recent_payments
            })
            return

        # 12. Staff
        if path == "/api/staff":
            cur.execute("SELECT * FROM staff ORDER BY id ASC;")
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            self.send_json(rows)
            return

        # 13. Student Attendance
        if path == "/api/attendance":
            cid = q('class_id')
            sec_id = q('section_id')
            date_str = q('date', datetime.now().strftime("%Y-%m-%d"))
            st_filter = q('student_id')

            if role == "student":
                st_filter = student_id_override

            if st_filter:
                cur.execute("""
                SELECT a.*, s.first_name, s.last_name, s.roll_no, s.reg_no
                FROM attendance a
                JOIN students s ON a.student_id = s.id
                WHERE a.student_id = ?
                ORDER BY a.attendance_date DESC LIMIT 30;
                """, (st_filter,))
            else:
                cur.execute("""
                SELECT s.id AS student_id, s.roll_no, s.first_name, s.last_name, s.reg_no,
                       IFNULL(a.status, 'Present') AS attendance_status,
                       a.remarks
                FROM students s
                LEFT JOIN attendance a ON a.student_id = s.id AND a.attendance_date = ?
                WHERE s.class_id = ? AND (? IS NULL OR s.section_id = ?) AND s.status = 'Active'
                ORDER BY s.roll_no ASC;
                """, (date_str, cid, sec_id, sec_id))

            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            self.send_json(rows)
            return

        # 14. Inquiries
        if path == "/api/inquiries":
            if role not in ["admin", "teacher"]:
                conn.close()
                self.send_json({"error": "Access denied to inquiries list."}, 403)
                return

            cur.execute("SELECT * FROM admission_inquiries ORDER BY id DESC;")
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            self.send_json(rows)
            return

        # 15. User Management (Admin only)
        if path == "/api/users":
            if role != "admin":
                conn.close()
                self.send_json({"error": "Access denied. Admin only."}, 403)
                return

            cur.execute("SELECT id, username, full_name, role, status, created_at FROM users ORDER BY id ASC;")
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            self.send_json(rows)
            return

        conn.close()
        self.send_json({"error": "Endpoint not found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self.parse_body()

        # Public Endpoints
        if path == "/api/auth/login":
            username = body.get('username', '').strip()
            password = body.get('password', '')
            user = authenticate_user(username, password)
            if not user:
                self.send_json({"error": "Invalid username or password"}, 401)
                return

            token, expires_at = create_session(user['id'])
            self.send_json({
                "success": True,
                "token": token,
                "expires_at": expires_at,
                "user": {
                    "id": user['id'],
                    "username": user['username'],
                    "full_name": user['full_name'],
                    "role": user['role'],
                    "linked_student_id": user['linked_student_id'],
                    "linked_staff_id": user['linked_staff_id']
                }
            })
            return

        if path == "/api/auth/logout":
            token = self.get_auth_token()
            if token:
                delete_session(token)
            self.send_json({"success": True, "message": "Logged out successfully."})
            return

        if path == "/api/inquiries":
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO admission_inquiries (
                applicant_name, applying_class, guardian_name, phone, email, address, previous_school, message, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending');
            """, (
                body.get('applicant_name'),
                body.get('applying_class'),
                body.get('guardian_name'),
                body.get('phone'),
                body.get('email', ''),
                body.get('address'),
                body.get('previous_school', ''),
                body.get('message', '')
            ))
            new_id = cur.lastrowid
            conn.commit()
            conn.close()
            self.send_json({"success": True, "id": new_id, "message": "Thank you! Your admission inquiry has been received. Our administration will contact you shortly."})
            return

        # Authenticated Endpoints Guard
        user = self.get_current_user()
        if not user:
            self.send_json({"error": "Authentication required. Please log in."}, 401)
            return

        role = user['role']

        # Change Password (Available to all authenticated roles including student)
        if path == "/api/auth/change-password":
            current_password = body.get('current_password', '').strip()
            new_password = body.get('new_password', '').strip()

            if not current_password or not new_password:
                self.send_json({"error": "Both current and new password are required."}, 400)
                return

            if len(new_password) < 6:
                self.send_json({"error": "New password must be at least 6 characters long."}, 400)
                return

            success, message = change_user_password(user['user_id'], current_password, new_password)
            if not success:
                self.send_json({"error": message}, 400)
                return

            self.send_json({"success": True, "message": message})
            return

        # Students cannot mutate data
        if role == "student":
            self.send_json({"error": "Access denied. Students have read-only portal access."}, 403)
            return

        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # 1. Add Student (Admin only)
            if path == "/api/students":
                if role not in ["admin"]:
                    conn.close()
                    self.send_json({"error": "Access denied. Only Administrators can admit students."}, 403)
                    return

                cur.execute("""
                INSERT INTO students (
                    reg_no, roll_no, first_name, last_name, name_np,
                    gender, dob_bs, dob_ad, class_id, section_id,
                    guardian_name, guardian_relation, guardian_phone, address,
                    blood_group, admission_date, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    body.get('reg_no'),
                    int(body.get('roll_no', 1)),
                    body.get('first_name'),
                    body.get('last_name'),
                    body.get('name_np', ''),
                    body.get('gender', 'Male'),
                    body.get('dob_bs'),
                    body.get('dob_ad', ''),
                    int(body.get('class_id')),
                    int(body.get('section_id')),
                    body.get('guardian_name'),
                    body.get('guardian_relation', 'Parent'),
                    body.get('guardian_phone'),
                    body.get('address'),
                    body.get('blood_group', 'O+'),
                    body.get('admission_date', datetime.now().strftime("%Y-%m-%d")),
                    body.get('status', 'Active')
                ))
                new_id = cur.lastrowid
                conn.commit()
                conn.close()
                self.send_json({"success": True, "id": new_id, "message": "Student admitted successfully."})
                return

            # 2. Bulk Marks Entry (Admin & Teacher)
            if path == "/api/marks/bulk":
                if role not in ["admin", "teacher"]:
                    conn.close()
                    self.send_json({"error": "Access denied. Only Teachers & Exam Officers can enter examination marks."}, 403)
                    return

                exam_id = int(body.get('exam_id'))
                subject_id = int(body.get('subject_id'))
                marks_list = body.get('marks', [])

                for item in marks_list:
                    sid = int(item.get('student_id'))
                    th = float(item.get('theory_obtained', 0))
                    pr = float(item.get('practical_obtained', 0))

                    cur.execute("""
                    INSERT INTO marks (exam_id, student_id, subject_id, theory_obtained, practical_obtained, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(exam_id, student_id, subject_id) DO UPDATE SET
                        theory_obtained = excluded.theory_obtained,
                        practical_obtained = excluded.practical_obtained,
                        updated_at = CURRENT_TIMESTAMP;
                    """, (exam_id, sid, subject_id, th, pr))

                conn.commit()
                conn.close()
                self.send_json({"success": True, "count": len(marks_list), "message": "Marks successfully saved and grades recomputed."})
                return

            # 3. Create Exam (Admin & Teacher)
            if path == "/api/exams":
                if role not in ["admin", "teacher"]:
                    conn.close()
                    self.send_json({"error": "Access denied."}, 403)
                    return

                cur.execute("""
                INSERT INTO exams (name, term, academic_year, start_date, end_date, is_published)
                VALUES (?, ?, ?, ?, ?, ?);
                """, (
                    body.get('name'),
                    body.get('term', 'First Term'),
                    body.get('academic_year', '2081'),
                    body.get('start_date'),
                    body.get('end_date'),
                    int(body.get('is_published', 1))
                ))
                new_id = cur.lastrowid
                conn.commit()
                conn.close()
                self.send_json({"success": True, "id": new_id, "message": "Examination term created."})
                return

            # 3b. Add Subject (Admin & Teacher)
            if path == "/api/subjects":
                if role not in ["admin", "teacher"]:
                    conn.close()
                    self.send_json({"error": "Access denied. Only faculty or administrators can add curriculum subjects."}, 403)
                    return

                class_id = int(body.get('class_id'))
                code = body.get('code', '').strip()
                name_en = body.get('name_en', '').strip()
                name_np = body.get('name_np', '').strip()
                credit_hours = float(body.get('credit_hours', 4.0))
                theory_full = float(body.get('theory_full_marks', 75.0))
                theory_pass = float(body.get('theory_pass_marks', 27.0))
                practical_full = float(body.get('practical_full_marks', 25.0))
                practical_pass = float(body.get('practical_pass_marks', 10.0))
                is_optional = int(body.get('is_optional', 0))

                cur.execute("""
                INSERT INTO subjects (
                    class_id, code, name_en, name_np, credit_hours,
                    theory_full_marks, theory_pass_marks, practical_full_marks, practical_pass_marks, is_optional
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (class_id, code, name_en, name_np, credit_hours, theory_full, theory_pass, practical_full, practical_pass, is_optional))
                new_id = cur.lastrowid
                conn.commit()
                conn.close()
                self.send_json({"success": True, "id": new_id, "message": "Curriculum subject added successfully."})
                return

            # 4. Generate Invoices (Admin & Accountant)
            if path == "/api/finance/invoices/generate":
                if role not in ["admin", "accountant"]:
                    conn.close()
                    self.send_json({"error": "Access denied. Only Finance officers can generate bills."}, 403)
                    return

                class_id = int(body.get('class_id'))
                month = body.get('month', 'Current')
                year = body.get('year', '2081')

                cur.execute("""
                SELECT fs.*, fh.name as fee_head_name
                FROM fee_structures fs
                JOIN fee_heads fh ON fs.fee_head_id = fh.id
                WHERE fs.class_id = ?;
                """, (class_id,))
                fee_items = cur.fetchall()

                if not fee_items:
                    conn.close()
                    self.send_json({"error": "No fee structure configured for this class"}, 400)
                    return

                total_amount = sum(f['amount'] for f in fee_items)

                cur.execute("SELECT id FROM students WHERE class_id = ? AND status = 'Active';", (class_id,))
                students = cur.fetchall()

                count = 0
                for st in students:
                    inv_no = f"INV-{year}-{class_id}{st['id']:04d}-{month[:3].upper()}"
                    cur.execute("""
                    INSERT OR IGNORE INTO invoices (invoice_no, student_id, month, year, total_amount, discount, fine, paid_amount, status, created_at)
                    VALUES (?, ?, ?, ?, ?, 0, 0, 0, 'Unpaid', ?);
                    """, (inv_no, st['id'], month, year, total_amount, datetime.now().strftime("%Y-%m-%d")))
                    inv_id = cur.lastrowid

                    if inv_id:
                        count += 1
                        for f in fee_items:
                            cur.execute("INSERT INTO invoice_items (invoice_id, fee_head_name, amount) VALUES (?, ?, ?);", (inv_id, f['fee_head_name'], f['amount']))

                conn.commit()
                conn.close()
                self.send_json({"success": True, "generated_count": count, "message": f"Generated {count} invoices for {month} {year}."})
                return

            # 5. Fee Payment / Collect Fee (Admin & Accountant)
            if path == "/api/finance/pay":
                if role not in ["admin", "accountant"]:
                    conn.close()
                    self.send_json({"error": "Access denied. Only Finance officers can collect fees."}, 403)
                    return

                invoice_id = int(body.get('invoice_id'))
                amount_paid = float(body.get('amount_paid'))
                discount = float(body.get('discount', 0))
                fine = float(body.get('fine', 0))
                payment_mode = body.get('payment_mode', 'Cash')
                trans_ref = body.get('transaction_ref', '')
                received_by = body.get('received_by', user['full_name'])
                notes = body.get('notes', '')

                cur.execute("SELECT * FROM invoices WHERE id = ?;", (invoice_id,))
                inv = cur.fetchone()
                if not inv:
                    conn.close()
                    self.send_json({"error": "Invoice not found"}, 404)
                    return

                new_paid = inv['paid_amount'] + amount_paid
                new_discount = inv['discount'] + discount
                new_fine = inv['fine'] + fine
                payable = inv['total_amount'] + new_fine - new_discount

                if new_paid >= payable:
                    status = 'Paid'
                elif new_paid > 0:
                    status = 'Partially Paid'
                else:
                    status = 'Unpaid'

                cur.execute("""
                UPDATE invoices
                SET paid_amount = ?, discount = ?, fine = ?, status = ?
                WHERE id = ?;
                """, (new_paid, new_discount, new_fine, status, invoice_id))

                receipt_no = f"REC-2081-{int(datetime.now().timestamp()) % 100000:05d}"
                cur.execute("""
                INSERT INTO payments (receipt_no, invoice_id, student_id, amount_paid, payment_mode, transaction_ref, payment_date, received_by, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    receipt_no,
                    invoice_id,
                    inv['student_id'],
                    amount_paid,
                    payment_mode,
                    trans_ref,
                    datetime.now().strftime("%Y-%m-%d"),
                    received_by,
                    notes
                ))

                conn.commit()
                conn.close()
                self.send_json({"success": True, "receipt_no": receipt_no, "message": "Payment collected and official receipt generated."})
                return

            # 6. Record Expense (Admin & Accountant)
            if path == "/api/finance/expenses":
                if role not in ["admin", "accountant"]:
                    conn.close()
                    self.send_json({"error": "Access denied. Only Finance officers can record expenses."}, 403)
                    return

                cur.execute("""
                INSERT INTO expenses (title, category, amount, payment_mode, expense_date, paid_to, approved_by, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    body.get('title'),
                    body.get('category'),
                    float(body.get('amount')),
                    body.get('payment_mode', 'Cash'),
                    body.get('expense_date', datetime.now().strftime("%Y-%m-%d")),
                    body.get('paid_to'),
                    body.get('approved_by', 'Principal'),
                    body.get('notes', '')
                ))
                new_id = cur.lastrowid
                conn.commit()
                conn.close()
                self.send_json({"success": True, "id": new_id, "message": "Expense recorded successfully."})
                return

            # 7. Add Staff (Admin only)
            if path == "/api/staff":
                if role != "admin":
                    conn.close()
                    self.send_json({"error": "Access denied. Admin only."}, 403)
                    return

                cur.execute("""
                INSERT INTO staff (emp_code, name_en, name_np, role, department, qualification, phone, email, joining_date, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    body.get('emp_code'),
                    body.get('name_en'),
                    body.get('name_np', ''),
                    body.get('role'),
                    body.get('department'),
                    body.get('qualification'),
                    body.get('phone'),
                    body.get('email', ''),
                    body.get('joining_date', datetime.now().strftime("%Y-%m-%d")),
                    body.get('status', 'Active')
                ))
                new_id = cur.lastrowid
                conn.commit()
                conn.close()
                self.send_json({"success": True, "id": new_id, "message": "Staff added successfully."})
                return

            # 8. Save Daily Attendance (Admin & Teacher)
            if path == "/api/attendance/bulk":
                if role not in ["admin", "teacher"]:
                    conn.close()
                    self.send_json({"error": "Access denied. Only Faculty can record attendance."}, 403)
                    return

                att_date = body.get('date', datetime.now().strftime("%Y-%m-%d"))
                records = body.get('attendance', [])

                for item in records:
                    sid = int(item.get('student_id'))
                    status = item.get('status', 'Present')
                    remarks = item.get('remarks', '')

                    cur.execute("""
                    INSERT INTO attendance (student_id, attendance_date, status, remarks)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(student_id, attendance_date) DO UPDATE SET
                        status = excluded.status,
                        remarks = excluded.remarks;
                    """, (sid, att_date, status, remarks))

                conn.commit()
                conn.close()
                self.send_json({"success": True, "count": len(records), "message": "Attendance successfully recorded."})
                return

            # 9. Add Notice (Admin & Teacher)
            if path == "/api/notices":
                if role not in ["admin", "teacher"]:
                    conn.close()
                    self.send_json({"error": "Access denied."}, 403)
                    return

                cur.execute("""
                INSERT INTO notices (title, category, content, posted_date, is_pinned, file_attachment)
                VALUES (?, ?, ?, ?, ?, ?);
                """, (
                    body.get('title'),
                    body.get('category', 'General'),
                    body.get('content'),
                    body.get('posted_date', datetime.now().strftime("%Y-%m-%d")),
                    int(body.get('is_pinned', 0)),
                    body.get('file_attachment')
                ))
                new_id = cur.lastrowid
                conn.commit()
                conn.close()
                self.send_json({"success": True, "id": new_id, "message": "Notice published."})
                return

            conn.close()
            self.send_json({"error": "Unknown POST route"}, 404)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json({"error": str(e)}, 500)

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self.parse_body()

        user = self.get_current_user()
        if not user:
            self.send_json({"error": "Authentication required."}, 401)
            return

        role = user['role']
        if role != "admin":
            self.send_json({"error": "Access denied. Admin only."}, 403)
            return

        try:
            conn = get_db_connection()
            cur = conn.cursor()

            if path.startswith("/api/students/"):
                student_id = int(path.split("/")[-1])
                cur.execute("""
                UPDATE students SET
                    roll_no = ?, first_name = ?, last_name = ?, name_np = ?,
                    gender = ?, dob_bs = ?, dob_ad = ?, class_id = ?, section_id = ?,
                    guardian_name = ?, guardian_relation = ?, guardian_phone = ?, address = ?,
                    blood_group = ?, status = ?
                WHERE id = ?;
                """, (
                    int(body.get('roll_no', 1)),
                    body.get('first_name'),
                    body.get('last_name'),
                    body.get('name_np', ''),
                    body.get('gender'),
                    body.get('dob_bs'),
                    body.get('dob_ad', ''),
                    int(body.get('class_id')),
                    int(body.get('section_id')),
                    body.get('guardian_name'),
                    body.get('guardian_relation'),
                    body.get('guardian_phone'),
                    body.get('address'),
                    body.get('blood_group'),
                    body.get('status', 'Active'),
                    student_id
                ))
                conn.commit()
                conn.close()
                self.send_json({"success": True, "message": "Student record updated."})
                return

            if path.startswith("/api/inquiries/"):
                inq_id = int(path.split("/")[-1])
                cur.execute("UPDATE admission_inquiries SET status = ? WHERE id = ?;", (body.get('status'), inq_id))
                conn.commit()
                conn.close()
                self.send_json({"success": True, "message": "Inquiry status updated."})
                return

            conn.close()
            self.send_json({"error": "Unknown PUT route"}, 404)

        except Exception as e:
            self.send_json({"error": str(e)}, 500)

def run_server(host=HOST, port=PORT):
    init_db()
    server = ThreadedHTTPServer((host, port), EMSRequestHandler)
    print(f"================================================================")
    print(f"  Shree Sagarmatha Secondary School & Sagarmatha EMS Server")
    print(f"  Protected with Multi-Level Role-Based Access Control (RBAC)")
    print(f"  Bhadrapur 2, Sagarmatha, Jhapa (Established 2034 BS)")
    print(f"  Running at: http://{host}:{port}")
    print(f"================================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server gracefully...")
        server.shutdown()

if __name__ == "__main__":
    run_server()
