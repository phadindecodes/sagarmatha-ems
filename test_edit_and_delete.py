"""
test_edit_and_delete.py - Verification suite for Staff, User, and Student Edit & Deletion
"""

import io
import json
import unittest
from app import EMSRequestHandler
from database import (
    authenticate_user, create_session, get_db_connection,
    update_staff_member, delete_staff_member, update_user_account, delete_user_account, delete_student_record
)

class MockRequest:
    def __init__(self, method="GET", path="/", body=None, token=None):
        self.method = method
        self.path = path
        self.body_bytes = json.dumps(body).encode("utf-8") if body else b""
        self.token = token

    def execute(self):
        handler = EMSRequestHandler.__new__(EMSRequestHandler)
        handler.rfile = io.BytesIO(self.body_bytes)
        handler.wfile = io.BytesIO()
        handler.path = self.path
        handler.command = self.method
        headers = {
            "Content-Length": str(len(self.body_bytes)),
            "Content-Type": "application/json"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        handler.headers = headers
        handler.request_version = "HTTP/1.1"

        status_code = [200]
        captured_headers = {}

        def mock_send_response(code, message=None):
            status_code[0] = code
        def mock_send_header(k, v):
            captured_headers[k] = v
        def mock_end_headers():
            pass

        handler.send_response = mock_send_response
        handler.send_header = mock_send_header
        handler.end_headers = mock_end_headers

        if self.method == "GET":
            handler.do_GET()
        elif self.method == "POST":
            handler.do_POST()
        elif self.method == "PUT":
            handler.do_PUT()
        elif self.method == "DELETE":
            handler.do_DELETE()

        handler.wfile.seek(0)
        out = handler.wfile.read()
        return status_code[0], json.loads(out.decode("utf-8")) if out else {}

class TestEditAndDelete(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        admin_user = authenticate_user("admin", "admin123")
        assert admin_user is not None
        cls.admin_token = create_session(admin_user['id'])[0]
        cls.admin_id = admin_user['id']

        teacher_user = authenticate_user("teacher", "teacher123")
        assert teacher_user is not None
        cls.teacher_token = create_session(teacher_user['id'])[0]

    def test_01_edit_staff_member_and_sync_user(self):
        # Create a test staff member with linked user
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO staff (emp_code, name_en, name_np, role, department, qualification, phone, email, status)
        VALUES ('EMP-TEST-99', 'Old Teacher Name', 'पुरानो शिक्षक', 'Science Teacher', 'Science', 'M.Sc.', '9800000001', 'test@school.edu.np', 'Active');
        """)
        staff_id = cur.lastrowid
        cur.execute("""
        INSERT INTO users (username, password_hash, salt, full_name, role, linked_staff_id, status)
        VALUES ('old.teacher', 'hash', 'salt', 'Old Teacher Name', 'teacher', ?, 'Active');
        """, (staff_id,))
        user_id = cur.lastrowid
        conn.commit()
        conn.close()

        # Admin updates staff name to "New Teacher Name"
        update_payload = {
            "name_en": "New Teacher Name",
            "name_np": "नयाँ शिक्षक",
            "role": "Senior Science Coordinator",
            "department": "Science",
            "qualification": "Ph.D.",
            "phone": "9811111111",
            "email": "new.teacher@school.edu.np",
            "status": "Active"
        }
        req = MockRequest("PUT", f"/api/staff/{staff_id}", body=update_payload, token=self.admin_token)
        code, data = req.execute()
        self.assertEqual(code, 200)
        self.assertTrue(data.get("success"))

        # Verify staff table was updated
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT name_en, role, qualification FROM staff WHERE id = ?;", (staff_id,))
        row = cur.fetchone()
        self.assertEqual(row['name_en'], "New Teacher Name")
        self.assertEqual(row['role'], "Senior Science Coordinator")

        # Verify linked user table full_name was automatically synchronized
        cur.execute("SELECT full_name FROM users WHERE id = ?;", (user_id,))
        u_row = cur.fetchone()
        self.assertEqual(u_row['full_name'], "New Teacher Name")
        conn.close()

    def test_02_edit_user_account_directly(self):
        # Admin updates user account username and full_name
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = 'old.teacher';")
        user_id = cur.fetchone()['id']
        conn.close()

        update_payload = {
            "username": "updated.teacher",
            "full_name": "Updated Teacher Profile",
            "role": "teacher"
        }
        req = MockRequest("PUT", f"/api/users/{user_id}", body=update_payload, token=self.admin_token)
        code, data = req.execute()
        self.assertEqual(code, 200)
        self.assertTrue(data.get("success"))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT username, full_name FROM users WHERE id = ?;", (user_id,))
        u_row = cur.fetchone()
        self.assertEqual(u_row['username'], "updated.teacher")
        self.assertEqual(u_row['full_name'], "Updated Teacher Profile")
        conn.close()

    def test_03_delete_staff_member(self):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM staff WHERE emp_code = 'EMP-TEST-99';")
        staff_id = cur.fetchone()['id']
        conn.close()

        # Admin deletes staff member
        req = MockRequest("DELETE", f"/api/staff/{staff_id}", token=self.admin_token)
        code, data = req.execute()
        self.assertEqual(code, 200)
        self.assertTrue(data.get("success"))

        # Verify staff and linked user are deleted
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM staff WHERE id = ?;", (staff_id,))
        self.assertIsNone(cur.fetchone())
        cur.execute("SELECT id FROM users WHERE username = 'updated.teacher';")
        self.assertIsNone(cur.fetchone())
        conn.close()

    def test_04_delete_user_safeguards(self):
        # 1. Admin cannot delete their own account
        req_self = MockRequest("DELETE", f"/api/users/{self.admin_id}", token=self.admin_token)
        code_self, data_self = req_self.execute()
        self.assertEqual(code_self, 400)
        self.assertIn("own currently logged-in account", data_self.get("error", ""))

        # 2. Create another user and delete it
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO users (username, password_hash, salt, full_name, role, status)
        VALUES ('temp.user', 'hash', 'salt', 'Temporary User', 'teacher', 'Active');
        """)
        temp_uid = cur.lastrowid
        conn.commit()
        conn.close()

        req_del = MockRequest("DELETE", f"/api/users/{temp_uid}", token=self.admin_token)
        code_del, data_del = req_del.execute()
        self.assertEqual(code_del, 200)
        self.assertTrue(data_del.get("success"))

    def test_05_edit_and_delete_student(self):
        # Create a test student with linked marks, invoice, and portal user
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO students (reg_no, roll_no, first_name, last_name, gender, dob_bs, class_id, section_id, guardian_name, guardian_phone, address, status)
        VALUES ('SSS-DEL-TEST', 88, 'Kritika', 'Sharma', 'Female', '2068-01-01', 10, 1, 'Prem Sharma', '9800000002', 'Bhadrapur', 'Active');
        """)
        st_id = cur.lastrowid
        cur.execute("""
        INSERT INTO users (username, password_hash, salt, full_name, role, linked_student_id, status)
        VALUES ('SSS-DEL-TEST', 'hash', 'salt', 'Kritika Sharma', 'student', ?, 'Active');
        """, (st_id,))
        conn.commit()
        conn.close()

        # 1. Edit student details
        edit_payload = {
            "roll_no": 89,
            "first_name": "Kritika",
            "last_name": "Sharma Dahal",
            "name_np": "कृतिका शर्मा दाहाल",
            "gender": "Female",
            "dob_bs": "2068-01-01",
            "dob_ad": "2011-04-14",
            "class_id": 10,
            "section_id": 1,
            "guardian_name": "Prem Sharma",
            "guardian_relation": "Father",
            "guardian_phone": "9800000002",
            "address": "Bhadrapur-2",
            "blood_group": "A+",
            "status": "Active"
        }
        req_edit = MockRequest("PUT", f"/api/students/{st_id}", body=edit_payload, token=self.admin_token)
        code_edit, data_edit = req_edit.execute()
        self.assertEqual(code_edit, 200)
        self.assertTrue(data_edit.get("success"))

        # Verify updated in DB
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT last_name, roll_no FROM students WHERE id = ?;", (st_id,))
        row = cur.fetchone()
        self.assertEqual(row['last_name'], "Sharma Dahal")
        self.assertEqual(row['roll_no'], 89)

        # 2. Delete student
        req_del = MockRequest("DELETE", f"/api/students/{st_id}", token=self.admin_token)
        code_del, data_del = req_del.execute()
        self.assertEqual(code_del, 200)
        self.assertTrue(data_del.get("success"))

        # Verify student and linked user are removed
        cur.execute("SELECT id FROM students WHERE id = ?;", (st_id,))
        self.assertIsNone(cur.fetchone())
        cur.execute("SELECT id FROM users WHERE username = 'SSS-DEL-TEST';")
        self.assertIsNone(cur.fetchone())
        conn.close()

    def test_06_rbac_blocks_non_admin(self):
        # Teacher cannot delete or edit staff
        req_put = MockRequest("PUT", "/api/staff/1", body={"name_en": "Hacked"}, token=self.teacher_token)
        code, _ = req_put.execute()
        self.assertEqual(code, 403)

        req_del = MockRequest("DELETE", "/api/staff/1", token=self.teacher_token)
        code, _ = req_del.execute()
        self.assertEqual(code, 403)

if __name__ == "__main__":
    unittest.main()
