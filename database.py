"""
database.py - SQLite Schema and Operations for Sagarmatha EMS
Shree Sagarmatha Secondary School, Bhadrapur 2, Jhapa (Est. 2034)
Includes Role-Based Access Control (RBAC) & Nepal CDC Grading Engine
"""

import sqlite3
import os
import json
import hashlib
import secrets
import urllib.request
import base64
from datetime import datetime, timedelta

def load_env_file():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

load_env_file()

DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "sagarmatha_ems.db"))
TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

# ============================================================================
# Turso Cloud SQLite (libSQL over HTTP Pipeline) Zero-Dependency Adapter
# ============================================================================
class TursoRow(dict):
    """Dictionary-like row that supports column name lookup, indexing, and dict() conversion."""
    def __init__(self, cols, vals):
        super().__init__(zip(cols, vals))
        self._cols = list(cols)
        self._vals = list(vals)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._vals[key]
        return super().__getitem__(key)

    def get(self, key, default=None):
        if isinstance(key, int):
            return self._vals[key] if 0 <= key < len(self._vals) else default
        return super().get(key, default)

    def keys(self):
        return self._cols

class TursoCursor:
    def __init__(self, conn):
        self.conn = conn
        self.description = None
        self.lastrowid = None
        self.rowcount = 0
        self._rows = []
        self._idx = 0

    def execute(self, sql, params=None):
        return self.conn._execute_stmt(self, sql, params)

    def executemany(self, sql, seq_of_params):
        for params in seq_of_params:
            self.execute(sql, params)
        return self

    def fetchone(self):
        if self._idx < len(self._rows):
            row = self._rows[self._idx]
            self._idx += 1
            return row
        return None

    def fetchall(self):
        if self._idx < len(self._rows):
            rows = self._rows[self._idx:]
            self._idx = len(self._rows)
            return rows
        return []

    def close(self):
        pass

class TursoHTTPConnection:
    def __init__(self, url, auth_token):
        clean_url = url
        if clean_url.startswith("libsql://"):
            clean_url = clean_url.replace("libsql://", "https://")
        elif not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            clean_url = f"https://{clean_url}"
        self.pipeline_url = f"{clean_url.rstrip('/')}/v2/pipeline"
        self.auth_token = auth_token
        self.row_factory = None

    def cursor(self):
        return TursoCursor(self)

    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def executemany(self, sql, seq_of_params):
        cur = self.cursor()
        cur.executemany(sql, seq_of_params)
        return cur

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    def _serialize_arg(self, val):
        if val is None:
            return {"type": "null"}
        elif isinstance(val, bool):
            return {"type": "integer", "value": "1" if val else "0"}
        elif isinstance(val, int):
            return {"type": "integer", "value": str(val)}
        elif isinstance(val, float):
            return {"type": "float", "value": val}
        elif isinstance(val, (bytes, bytearray)):
            return {"type": "blob", "base64": base64.b64encode(val).decode("ascii")}
        else:
            return {"type": "text", "value": str(val)}

    def _deserialize_val(self, v):
        if not isinstance(v, dict):
            return v
        vtype = v.get("type")
        if vtype == "null":
            return None
        elif vtype == "integer":
            try:
                return int(v.get("value", 0))
            except (ValueError, TypeError):
                return v.get("value")
        elif vtype == "float":
            try:
                return float(v.get("value", 0.0))
            except (ValueError, TypeError):
                return v.get("value")
        elif vtype == "text":
            return str(v.get("value", ""))
        elif vtype == "blob":
            return base64.b64decode(v.get("base64", ""))
        return v.get("value")

    def _execute_stmt(self, cur, sql, params=None):
        args = []
        if params is not None:
            if isinstance(params, (list, tuple)):
                args = [self._serialize_arg(p) for p in params]
            elif isinstance(params, dict):
                for k, v in params.items():
                    args.append(self._serialize_arg(v))

        payload = {
            "requests": [
                {
                    "type": "execute",
                    "stmt": {
                        "sql": sql,
                        "args": args
                    }
                },
                {"type": "close"}
            ]
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.pipeline_url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.auth_token}",
                "Content-Type": "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=20) as res:
            body = res.read().decode("utf-8")
            resp_json = json.loads(body)

        results = resp_json.get("results", [])
        if not results:
            return cur

        first_res = results[0]
        if first_res.get("type") == "error":
            err_msg = first_res.get("error", {}).get("message", "Database error")
            raise RuntimeError(f"Turso Error: {err_msg}")

        resp_obj = first_res.get("response", {})
        result_obj = resp_obj.get("result", {})

        cols = [c.get("name") if isinstance(c, dict) else str(c) for c in result_obj.get("cols", [])]
        cur.description = [(c, None, None, None, None, None, None) for c in cols]

        last_id = result_obj.get("last_insert_rowid")
        if last_id is not None:
            try:
                cur.lastrowid = int(last_id)
            except (ValueError, TypeError):
                cur.lastrowid = last_id
        else:
            cur.lastrowid = None

        cur.rowcount = result_obj.get("affected_row_count", 0)

        raw_rows = result_obj.get("rows", [])
        cur._rows = []
        for r in raw_rows:
            parsed_vals = [self._deserialize_val(cell) for cell in r]
            cur._rows.append(TursoRow(cols, parsed_vals))
        cur._idx = 0
        return cur

def get_db_connection():
    turso_url = os.environ.get("TURSO_DATABASE_URL")
    turso_token = os.environ.get("TURSO_AUTH_TOKEN")
    if turso_url and turso_token:
        return TursoHTTPConnection(turso_url, turso_token)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# ============================================================================
# Authentication & Cryptographic Helpers
# ============================================================================
def hash_password(password, salt=None):
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return key.hex(), salt

def verify_password(password, salt, expected_hash):
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return secrets.compare_digest(key.hex(), expected_hash)

def create_user(username, password, full_name, role, linked_student_id=None, linked_staff_id=None):
    pwd_hash, salt = hash_password(password)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO users (username, password_hash, salt, full_name, role, linked_student_id, linked_staff_id, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'Active');
    """, (username, pwd_hash, salt, full_name, role, linked_student_id, linked_staff_id))
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    return user_id

def authenticate_user(username, password):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ? AND status = 'Active';", (username,))
    user = cur.fetchone()
    conn.close()

    if not user:
        return None

    if verify_password(password, user['salt'], user['password_hash']):
        return dict(user)
    return None

def create_session(user_id, duration_hours=24):
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now() + timedelta(hours=duration_hours)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO sessions (token, user_id, expires_at)
    VALUES (?, ?, ?);
    """, (token, user_id, expires_at))
    conn.commit()
    conn.close()
    return token, expires_at

def validate_session(token):
    if not token:
        return None
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT s.*, u.id as user_id, u.username, u.full_name, u.role, u.linked_student_id, u.linked_staff_id
    FROM sessions s
    JOIN users u ON s.user_id = u.id
    WHERE s.token = ? AND s.expires_at > CURRENT_TIMESTAMP AND u.status = 'Active';
    """, (token,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_session(token):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM sessions WHERE token = ?;", (token,))
    conn.commit()
    conn.close()

def change_user_password(user_id, current_password, new_password):
    if not new_password or len(new_password) < 6:
        return False, "New password must be at least 6 characters long."
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, password_hash, salt FROM users WHERE id = ? AND status = 'Active';", (user_id,))
    user = cur.fetchone()
    if not user:
        conn.close()
        return False, "User not found or account is inactive."

    if not verify_password(current_password, user['salt'], user['password_hash']):
        conn.close()
        return False, "Current password does not match."

    new_hash, new_salt = hash_password(new_password)
    cur.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?;", (new_hash, new_salt, user_id))
    conn.commit()
    conn.close()
    return True, "Password has been successfully changed."

def reset_user_password(user_id, new_password):
    if not new_password or len(new_password) < 6:
        return False, "Password must be at least 6 characters long."
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE id = ?;", (user_id,))
    if not cur.fetchone():
        conn.close()
        return False, "User not found."
    new_hash, new_salt = hash_password(new_password)
    cur.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?;", (new_hash, new_salt, user_id))
    cur.execute("DELETE FROM sessions WHERE user_id = ?;", (user_id,))
    conn.commit()
    conn.close()
    return True, "Password has been successfully reset."

def toggle_user_status(user_id, new_status=None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, status FROM users WHERE id = ?;", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "User not found."
    
    current_status = row['status'] if isinstance(row, dict) else row[1]
    if not new_status:
        new_status = 'Inactive' if current_status == 'Active' else 'Active'
    
    cur.execute("UPDATE users SET status = ? WHERE id = ?;", (new_status, user_id))
    if new_status == 'Inactive':
        cur.execute("DELETE FROM sessions WHERE user_id = ?;", (user_id,))
    conn.commit()
    conn.close()
    return True, f"User status updated to {new_status}."

def get_student_user(student_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, full_name, role, status, created_at FROM users WHERE linked_student_id = ?;", (student_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_staff_user(staff_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, full_name, role, status, created_at FROM users WHERE linked_staff_id = ?;", (staff_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def update_staff_member(staff_id, data):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM staff WHERE id = ?;", (staff_id,))
    if not cur.fetchone():
        conn.close()
        return False, "Staff member not found."

    cur.execute("""
    UPDATE staff SET
        name_en = ?,
        name_np = ?,
        role = ?,
        department = ?,
        qualification = ?,
        phone = ?,
        email = ?,
        status = ?
    WHERE id = ?;
    """, (
        data.get('name_en', '').strip(),
        data.get('name_np', '').strip(),
        data.get('role', '').strip(),
        data.get('department', '').strip(),
        data.get('qualification', '').strip(),
        data.get('phone', '').strip(),
        data.get('email', '').strip(),
        data.get('status', 'Active'),
        staff_id
    ))

    # Keep linked user account's full_name in sync if linked
    name_en = data.get('name_en', '').strip()
    if name_en:
        cur.execute("UPDATE users SET full_name = ? WHERE linked_staff_id = ?;", (name_en, staff_id))

    conn.commit()
    conn.close()
    return True, "Staff record updated successfully."

def delete_staff_member(staff_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM staff WHERE id = ?;", (staff_id,))
    if not cur.fetchone():
        conn.close()
        return False, "Staff member not found."

    # If there is a linked user, remove sessions and delete user account
    cur.execute("SELECT id FROM users WHERE linked_staff_id = ?;", (staff_id,))
    user_rows = cur.fetchall()
    for u in user_rows:
        uid = u['id'] if isinstance(u, dict) else u[0]
        cur.execute("DELETE FROM sessions WHERE user_id = ?;", (uid,))
        cur.execute("DELETE FROM users WHERE id = ?;", (uid,))

    cur.execute("DELETE FROM staff WHERE id = ?;", (staff_id,))
    conn.commit()
    conn.close()
    return True, "Staff member and associated login account removed successfully."

def update_user_account(user_id, full_name, username, role):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username FROM users WHERE id = ?;", (user_id,))
    existing = cur.fetchone()
    if not existing:
        conn.close()
        return False, "User not found."

    username = username.strip()
    full_name = full_name.strip()
    cur.execute("SELECT id FROM users WHERE username = ? AND id != ?;", (username, user_id))
    if cur.fetchone():
        conn.close()
        return False, f"Username '{username}' is already in use."

    cur.execute("""
    UPDATE users SET
        full_name = ?,
        username = ?,
        role = ?
    WHERE id = ?;
    """, (full_name, username, role, user_id))

    # If linked to staff, also update staff name_en
    cur.execute("SELECT linked_staff_id FROM users WHERE id = ?;", (user_id,))
    row = cur.fetchone()
    if row:
        staff_id = row['linked_staff_id'] if isinstance(row, dict) else row[0]
        if staff_id:
            cur.execute("UPDATE staff SET name_en = ? WHERE id = ?;", (full_name, staff_id))

    conn.commit()
    conn.close()
    return True, "User account updated successfully."

def delete_user_account(user_id, current_user_id=None):
    if current_user_id and str(user_id) == str(current_user_id):
        return False, "You cannot delete your own currently logged-in account."

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, role, username FROM users WHERE id = ?;", (user_id,))
    user = cur.fetchone()
    if not user:
        conn.close()
        return False, "User not found."

    role = user['role'] if isinstance(user, dict) else user[1]
    if role == 'admin':
        # Ensure we don't delete the last admin
        cur.execute("SELECT COUNT(*) as admin_count FROM users WHERE role = 'admin' AND status = 'Active';")
        cnt_row = cur.fetchone()
        cnt = cnt_row['admin_count'] if isinstance(cnt_row, dict) else cnt_row[0]
        if cnt <= 1:
            conn.close()
            return False, "Cannot delete the sole administrator account."

    cur.execute("DELETE FROM sessions WHERE user_id = ?;", (user_id,))
    cur.execute("DELETE FROM users WHERE id = ?;", (user_id,))
    conn.commit()
    conn.close()
    return True, "User account deleted successfully."

def delete_student_record(student_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, reg_no FROM students WHERE id = ?;", (student_id,))
    st = cur.fetchone()
    if not st:
        conn.close()
        return False, "Student not found."

    # Delete linked user account and sessions
    cur.execute("SELECT id FROM users WHERE linked_student_id = ?;", (student_id,))
    users = cur.fetchall()
    for u in users:
        uid = u['id'] if isinstance(u, dict) else u[0]
        cur.execute("DELETE FROM sessions WHERE user_id = ?;", (uid,))
        cur.execute("DELETE FROM users WHERE id = ?;", (uid,))

    # Cascading deletes
    cur.execute("DELETE FROM marks WHERE student_id = ?;", (student_id,))
    cur.execute("DELETE FROM attendance WHERE student_id = ?;", (student_id,))
    cur.execute("DELETE FROM invoices WHERE student_id = ?;", (student_id,))
    cur.execute("DELETE FROM students WHERE id = ?;", (student_id,))
    conn.commit()
    conn.close()
    return True, "Student record and associated records deleted successfully."

def bulk_create_student_accounts(class_id=None, default_password="sagarmatha@2081"):
    conn = get_db_connection()
    cur = conn.cursor()

    query = """
    SELECT s.id, s.reg_no, s.roll_no, s.first_name, s.last_name, s.name_np, c.name as class_name, sec.name as section_name
    FROM students s
    JOIN classes c ON s.class_id = c.id
    JOIN sections sec ON s.section_id = sec.id
    WHERE s.status = 'Active'
    """
    params = []
    if class_id:
        query += " AND s.class_id = ?"
        params.append(class_id)
    query += " ORDER BY c.numeric_level ASC, sec.name ASC, s.roll_no ASC;"

    cur.execute(query, tuple(params))
    students = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT linked_student_id, username FROM users WHERE linked_student_id IS NOT NULL;")
    existing_users = {r['linked_student_id']: r['username'] for r in [dict(row) for row in cur.fetchall()]}

    created_accounts = []
    pwd_hash, salt = hash_password(default_password)

    for st in students:
        sid = st['id']
        reg = st['reg_no'].strip()
        full_name = f"{st['first_name']} {st['last_name']}".strip()

        if sid in existing_users:
            created_accounts.append({
                "student_id": sid,
                "student_name": full_name,
                "name_np": st.get('name_np', ''),
                "class_name": st['class_name'],
                "section_name": st['section_name'],
                "roll_no": st['roll_no'],
                "reg_no": reg,
                "username": existing_users[sid],
                "default_password": "(Existing Account - Password Preserved)",
                "created": False
            })
        else:
            username = reg
            cur.execute("""
            INSERT OR IGNORE INTO users (username, password_hash, salt, full_name, role, linked_student_id, status)
            VALUES (?, ?, ?, ?, 'student', ?, 'Active');
            """, (username, pwd_hash, salt, full_name, sid))
            
            created_accounts.append({
                "student_id": sid,
                "student_name": full_name,
                "name_np": st.get('name_np', ''),
                "class_name": st['class_name'],
                "section_name": st['section_name'],
                "roll_no": st['roll_no'],
                "reg_no": reg,
                "username": username,
                "default_password": default_password,
                "created": True
            })

    conn.commit()
    conn.close()
    new_count = sum(1 for a in created_accounts if a['created'])
    return {
        "success": True,
        "total_students": len(created_accounts),
        "newly_created": new_count,
        "existing": len(created_accounts) - new_count,
        "accounts": created_accounts
    }

# ============================================================================
# Nepal CDC Grading Engine (Letter Grading Directive 2078/2080)
# ============================================================================
def calculate_grade_and_gp(score_percentage):
    pct = round(score_percentage, 2)
    if pct >= 90:
        return ("A+", 4.0, "Outstanding")
    elif pct >= 80:
        return ("A", 3.6, "Excellent")
    elif pct >= 70:
        return ("B+", 3.2, "Very Good")
    elif pct >= 60:
        return ("B", 2.8, "Good")
    elif pct >= 50:
        return ("C+", 2.4, "Satisfactory")
    elif pct >= 40:
        return ("C", 2.0, "Acceptable")
    elif pct >= 35:
        return ("D", 1.6, "Basic")
    else:
        return ("NG", 0.0, "Non-Graded")

def calculate_subject_evaluation(theory_obtained, theory_full, practical_obtained, practical_full, credit_hours):
    th_pct = (theory_obtained / theory_full * 100) if theory_full > 0 else 0
    th_grade, th_gp, th_desc = calculate_grade_and_gp(th_pct)

    has_practical = practical_full > 0
    pr_grade, pr_gp, pr_desc = ("-", 0.0, "-")
    pr_pct = 0

    if has_practical:
        pr_pct = (practical_obtained / practical_full * 100) if practical_full > 0 else 0
        pr_grade, pr_gp, pr_desc = calculate_grade_and_gp(pr_pct)

    theory_pass = th_pct >= 35.0
    practical_pass = (not has_practical) or (pr_pct >= 40.0)

    total_obtained = theory_obtained + (practical_obtained if has_practical else 0)
    total_full = theory_full + (practical_full if has_practical else 0)
    total_pct = (total_obtained / total_full * 100) if total_full > 0 else 0

    if not theory_pass or not practical_pass:
        final_grade = "NG"
        final_gp = 0.0
        final_desc = "Non-Graded"
    else:
        final_grade, final_gp, final_desc = calculate_grade_and_gp(total_pct)

    return {
        "theory_obtained": theory_obtained,
        "theory_full": theory_full,
        "theory_pct": round(th_pct, 1),
        "theory_grade": th_grade,
        "theory_gp": th_gp,
        "practical_obtained": practical_obtained if has_practical else None,
        "practical_full": practical_full if has_practical else None,
        "practical_pct": round(pr_pct, 1) if has_practical else None,
        "practical_grade": pr_grade,
        "practical_gp": pr_gp,
        "total_obtained": total_obtained,
        "total_full": total_full,
        "total_pct": round(total_pct, 1),
        "final_grade": final_grade,
        "final_gp": final_gp,
        "credit_hours": credit_hours,
        "weighted_gp": round(final_gp * credit_hours, 2),
        "remarks": final_desc
    }

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # School Info & Settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS school_info (
        id INTEGER PRIMARY KEY,
        name_en TEXT NOT NULL,
        name_np TEXT NOT NULL,
        tagline_en TEXT,
        tagline_np TEXT,
        address_en TEXT NOT NULL,
        address_np TEXT NOT NULL,
        established_bs INTEGER NOT NULL,
        email TEXT,
        phone TEXT,
        website TEXT,
        academic_year TEXT NOT NULL
    );
    """)

    # Users (RBAC)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL,             -- 'admin', 'teacher', 'accountant', 'student'
        linked_student_id INTEGER,
        linked_staff_id INTEGER,
        status TEXT DEFAULT 'Active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (linked_student_id) REFERENCES students(id) ON DELETE SET NULL,
        FOREIGN KEY (linked_staff_id) REFERENCES staff(id) ON DELETE SET NULL
    );
    """)

    # User Sessions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # Classes & Streams (ECD to 12)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        level TEXT NOT NULL,
        numeric_level INTEGER NOT NULL,
        stream TEXT DEFAULT 'General'
    );
    """)

    # Sections
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
    );
    """)

    # Students
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reg_no TEXT UNIQUE NOT NULL,
        roll_no INTEGER NOT NULL,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        name_np TEXT,
        gender TEXT NOT NULL,
        dob_bs TEXT NOT NULL,
        dob_ad TEXT,
        class_id INTEGER NOT NULL,
        section_id INTEGER NOT NULL,
        guardian_name TEXT NOT NULL,
        guardian_relation TEXT DEFAULT 'Parent',
        guardian_phone TEXT NOT NULL,
        address TEXT NOT NULL,
        blood_group TEXT,
        admission_date TEXT,
        status TEXT DEFAULT 'Active',
        photo_url TEXT,
        FOREIGN KEY (class_id) REFERENCES classes(id),
        FOREIGN KEY (section_id) REFERENCES sections(id)
    );
    """)

    # Subjects
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_id INTEGER NOT NULL,
        code TEXT NOT NULL,
        name_en TEXT NOT NULL,
        name_np TEXT,
        credit_hours REAL NOT NULL DEFAULT 4.0,
        theory_full_marks REAL NOT NULL DEFAULT 75.0,
        theory_pass_marks REAL NOT NULL DEFAULT 27.0,
        practical_full_marks REAL NOT NULL DEFAULT 25.0,
        practical_pass_marks REAL NOT NULL DEFAULT 10.0,
        is_optional INTEGER DEFAULT 0,
        FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
    );
    """)

    # Examination Terms
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS exams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        term TEXT NOT NULL,
        academic_year TEXT NOT NULL,
        start_date TEXT,
        end_date TEXT,
        is_published INTEGER DEFAULT 1
    );
    """)

    # Student Marks
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS marks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        subject_id INTEGER NOT NULL,
        theory_obtained REAL NOT NULL DEFAULT 0,
        practical_obtained REAL NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(exam_id, student_id, subject_id),
        FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
        FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
    );
    """)

    # Fee Heads
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fee_heads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        is_recurring INTEGER DEFAULT 1
    );
    """)

    # Class Fee Structure
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fee_structures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_id INTEGER NOT NULL,
        fee_head_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
        FOREIGN KEY (fee_head_id) REFERENCES fee_heads(id) ON DELETE CASCADE,
        UNIQUE(class_id, fee_head_id)
    );
    """)

    # Invoices
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_no TEXT UNIQUE NOT NULL,
        student_id INTEGER NOT NULL,
        month TEXT NOT NULL,
        year TEXT NOT NULL,
        total_amount REAL NOT NULL,
        discount REAL DEFAULT 0,
        fine REAL DEFAULT 0,
        paid_amount REAL DEFAULT 0,
        status TEXT DEFAULT 'Unpaid',
        created_at TEXT NOT NULL,
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    );
    """)

    # Invoice Items
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoice_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL,
        fee_head_name TEXT NOT NULL,
        amount REAL NOT NULL,
        FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
    );
    """)

    # Fee Receipts (Payments)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt_no TEXT UNIQUE NOT NULL,
        invoice_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        amount_paid REAL NOT NULL,
        payment_mode TEXT DEFAULT 'Cash',
        transaction_ref TEXT,
        payment_date TEXT NOT NULL,
        received_by TEXT NOT NULL DEFAULT 'Accountant',
        notes TEXT,
        FOREIGN KEY (invoice_id) REFERENCES invoices(id),
        FOREIGN KEY (student_id) REFERENCES students(id)
    );
    """)

    # School Expenses
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        payment_mode TEXT DEFAULT 'Cash',
        expense_date TEXT NOT NULL,
        paid_to TEXT NOT NULL,
        approved_by TEXT NOT NULL,
        notes TEXT
    );
    """)

    # Staff / Teachers
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS staff (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_code TEXT UNIQUE NOT NULL,
        name_en TEXT NOT NULL,
        name_np TEXT,
        role TEXT NOT NULL,
        department TEXT NOT NULL,
        qualification TEXT NOT NULL,
        phone TEXT NOT NULL,
        email TEXT,
        joining_date TEXT,
        status TEXT DEFAULT 'Active'
    );
    """)

    # Student Attendance
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        attendance_date TEXT NOT NULL,
        status TEXT NOT NULL,
        remarks TEXT,
        UNIQUE(student_id, attendance_date),
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
    );
    """)

    # Public Notices
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        content TEXT NOT NULL,
        posted_date TEXT NOT NULL,
        is_pinned INTEGER DEFAULT 0,
        file_attachment TEXT
    );
    """)

    # Admission Inquiries
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admission_inquiries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        applicant_name TEXT NOT NULL,
        applying_class TEXT NOT NULL,
        guardian_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        email TEXT,
        address TEXT NOT NULL,
        previous_school TEXT,
        message TEXT,
        status TEXT DEFAULT 'Pending',
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Photo Gallery
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gallery_photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        title_np TEXT,
        category TEXT NOT NULL,          -- 'Campus', 'Academic', 'Sports', 'Events'
        image_url TEXT NOT NULL,
        caption TEXT,
        caption_np TEXT,
        featured INTEGER DEFAULT 0,
        sort_order INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

        # Ensure default school info exists
    try:
        cursor.execute("SELECT COUNT(*) as cnt FROM school_info;")
        si_row = cursor.fetchone()
        si_count = si_row['cnt'] if isinstance(si_row, dict) else (si_row[0] if si_row else 0)
        if si_count == 0:
            cursor.execute("""
            INSERT INTO school_info (
                id, name_en, name_np, tagline_en, tagline_np,
                address_en, address_np, established_bs, email, phone, website, academic_year
            ) VALUES (
                1,
                'Shree Sagarmatha Secondary School',
                'श्री सगरमाथा माध्यमिक विद्यालय',
                'Centrally Located Community School Dedicated to Academic Excellence & Holistic Growth',
                'सामुदायिक शिक्षामा उत्कृष्टता, प्रविधिमैत्री सिकाइ र समग्र विकास',
                'Bhadrapur-2, Sagarmatha, Jhapa, Koshi Province, Nepal',
                'भद्रपुर-२, सगरमाथा, झापा, कोशी प्रदेश, नेपाल',
                2034,
                'info@sagarmathaschool.edu.np',
                '023-520134, 9842601234',
                'www.sagarmathaschool.edu.np',
                '2081'
            );
            """)
    except Exception as e:
        print(f"School info init note: {e}")

    # Ensure default RBAC user accounts exist so login NEVER fails on blank databases
    try:
        cursor.execute("SELECT COUNT(*) as cnt FROM users;")
        u_row = cursor.fetchone()
        u_count = u_row['cnt'] if isinstance(u_row, dict) else (u_row[0] if u_row else 0)
        if u_count == 0:
            default_accounts = [
                ('admin', 'admin123', 'Ram Prasad Adhikari (Principal)', 'admin'),
                ('teacher', 'teacher123', 'Dr. Janak Raj Bhattarai (Exam Coordinator)', 'teacher'),
                ('accountant', 'account123', 'Manoj Kumar Shrestha (Senior Bursar)', 'accountant'),
                ('student10', 'student123', 'Aayush Adhikari (Student Class 10)', 'student')
            ]
            for uname, pwd, fname, role in default_accounts:
                pwd_hash, salt = hash_password(pwd)
                cursor.execute("""
                INSERT INTO users (username, password_hash, salt, full_name, role, status)
                VALUES (?, ?, ?, ?, ?, 'Active');
                """, (uname, pwd_hash, salt, fname, role))
            print("Default RBAC accounts initialized successfully.")
    except Exception as e:
        print(f"Users init note: {e}")

    conn.commit()
    conn.close()
    print("Database initialized successfully with RBAC.")

if __name__ == "__main__":
    init_db()
