"""
test_user_management.py - Test Suite for User Accounts, Teacher & Student Login Creation, Bulk Accounts, and Admin Resets
"""

import io
import json
import unittest
from app import EMSRequestHandler
from database import (
    authenticate_user, create_session, validate_session, get_db_connection,
    reset_user_password, toggle_user_status, bulk_create_student_accounts, hash_password
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

        handler.wfile.seek(0)
        out = handler.wfile.read()
        return status_code[0], json.loads(out.decode("utf-8")) if out else {}

class TestUserManagement(unittest.TestCase):

    @classmethod
    def clean_test_data(cls):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE username IN ('janak.bhattarai', 'SSS-2081-9999');")
        cur.execute("DELETE FROM students WHERE reg_no = 'SSS-2081-9999';")
        conn.commit()
        conn.close()

    @classmethod
    def setUpClass(cls):
        cls.clean_test_data()
        # Authenticate admin
        admin_user = authenticate_user("admin", "admin123")
        assert admin_user is not None, "Admin user must exist"
        cls.admin_token = create_session(admin_user['id'])[0]

        # Authenticate teacher
        teacher_user = authenticate_user("teacher", "teacher123")
        assert teacher_user is not None, "Teacher user must exist"
        cls.teacher_token = create_session(teacher_user['id'])[0]

    @classmethod
    def tearDownClass(cls):
        cls.clean_test_data()

    def test_01_get_users_admin_only(self):
        # Admin can view all users
        req_admin = MockRequest("GET", "/api/users", token=self.admin_token)
        code, data = req_admin.execute()
        self.assertEqual(code, 200)
        self.assertIsInstance(data, list)
        self.assertTrue(len(data) >= 1)
        # Verify passwords and hashes are omitted
        for u in data:
            self.assertNotIn("password_hash", u)
            self.assertNotIn("salt", u)

        # Teacher cannot view users management API
        req_teacher = MockRequest("GET", "/api/users", token=self.teacher_token)
        code_t, data_t = req_teacher.execute()
        self.assertEqual(code_t, 403)
        self.assertIn("Access denied", data_t.get("error", ""))

    def test_02_create_teacher_account(self):
        # Admin creates a new dedicated teacher account
        payload = {
            "username": "janak.bhattarai",
            "password": "TeacherPassword@2081",
            "full_name": "Janak Bhattarai",
            "role": "teacher"
        }
        req = MockRequest("POST", "/api/users", body=payload, token=self.admin_token)
        code, data = req.execute()
        self.assertIn(code, [200, 201])
        self.assertTrue(data.get("success"))

        # Verify teacher can authenticate with new credentials
        authenticated = authenticate_user("janak.bhattarai", "TeacherPassword@2081")
        self.assertIsNotNone(authenticated)
        self.assertEqual(authenticated['role'], "teacher")
        self.assertEqual(authenticated['full_name'], "Janak Bhattarai")

    def test_03_bulk_generate_student_accounts(self):
        # Bulk generate student accounts for all active students with default password
        payload = {
            "default_password": "sagarmatha@2081"
        }
        req = MockRequest("POST", "/api/students/generate-accounts", body=payload, token=self.admin_token)
        code, data = req.execute()
        self.assertEqual(code, 200)
        self.assertTrue(data.get("success"))
        self.assertIn("accounts", data)
        self.assertIsInstance(data["accounts"], list)
        self.assertTrue(len(data["accounts"]) > 0)

        # Inspect first generated student account
        first_acc = data["accounts"][0]
        self.assertEqual(first_acc["username"], first_acc["reg_no"])
        self.assertIn("student_name", first_acc)
        self.assertIn("class_name", first_acc)

        # Verify the student can log in using their reg_no and default password
        student_user = authenticate_user(first_acc["username"], "sagarmatha@2081")
        self.assertIsNotNone(student_user)
        self.assertEqual(student_user["role"], "student")
        self.assertEqual(student_user["linked_student_id"], first_acc["student_id"])

    def test_04_admin_reset_password(self):
        # Find teacher user to reset
        req = MockRequest("GET", "/api/users", token=self.admin_token)
        code, users = req.execute()
        self.assertEqual(code, 200)
        target_user = next(u for u in users if u['username'] == "janak.bhattarai")
        user_id = target_user['id']

        # Admin resets password to a new one
        reset_payload = {"new_password": "NewSecretPassword@2081"}
        req_reset = MockRequest("PUT", f"/api/users/{user_id}/reset-password", body=reset_payload, token=self.admin_token)
        code, data = req_reset.execute()
        self.assertEqual(code, 200)
        self.assertTrue(data.get("success"))

        # Old password should fail
        old_auth = authenticate_user("janak.bhattarai", "TeacherPassword@2081")
        self.assertIsNone(old_auth)

        # New password should succeed
        new_auth = authenticate_user("janak.bhattarai", "NewSecretPassword@2081")
        self.assertIsNotNone(new_auth)

    def test_05_admin_toggle_user_status(self):
        # Find teacher user
        req = MockRequest("GET", "/api/users", token=self.admin_token)
        code, users = req.execute()
        self.assertEqual(code, 200)
        target_user = next(u for u in users if u['username'] == "janak.bhattarai")
        user_id = target_user['id']

        # Suspend user
        status_payload = {"status": "Suspended"}
        req_suspend = MockRequest("PUT", f"/api/users/{user_id}/status", body=status_payload, token=self.admin_token)
        code, data = req_suspend.execute()
        self.assertEqual(code, 200)
        self.assertEqual(data.get("status"), "Suspended")

        # Suspended user cannot authenticate
        auth_suspended = authenticate_user("janak.bhattarai", "NewSecretPassword@2081")
        self.assertIsNone(auth_suspended)

        # Reactivate user
        reactivate_payload = {"status": "Active"}
        req_active = MockRequest("PUT", f"/api/users/{user_id}/status", body=reactivate_payload, token=self.admin_token)
        code_act, data_act = req_active.execute()
        self.assertEqual(code_act, 200)
        self.assertEqual(data_act.get("status"), "Active")

        # Now can authenticate again
        auth_active = authenticate_user("janak.bhattarai", "NewSecretPassword@2081")
        self.assertIsNotNone(auth_active)

    def test_06_student_admission_auto_creates_portal_account(self):
        # Enrolling a new student automatically generates their login account
        student_payload = {
            "reg_no": "SSS-2081-9999",
            "roll_no": 99,
            "first_name": "Dipen",
            "last_name": "Adhikari",
            "name_np": "दिपेन अधिकारी",
            "gender": "Male",
            "dob_bs": "2067-04-12",
            "dob_ad": "2010-07-28",
            "class_id": 10,
            "section_id": 1,
            "guardian_name": "Govinda Adhikari",
            "guardian_relation": "Father",
            "guardian_phone": "9842600000",
            "address": "Bhadrapur-2",
            "blood_group": "B+",
            "status": "Active"
        }
        req = MockRequest("POST", "/api/students", body=student_payload, token=self.admin_token)
        code, data = req.execute()
        self.assertIn(code, [200, 201])
        self.assertTrue(data.get("success"))

        # Verify portal user was auto-created with username = reg_no
        auth_new_student = authenticate_user("SSS-2081-9999", "sagarmatha@2081")
        self.assertIsNotNone(auth_new_student)
        self.assertEqual(auth_new_student["role"], "student")
        self.assertEqual(auth_new_student["username"], "SSS-2081-9999")

if __name__ == "__main__":
    unittest.main()
