"""
test_rbac.py - Verification Test Suite for Sagarmatha EMS Role-Based Access Control
"""

import io
import json
import unittest
from app import EMSRequestHandler
from database import authenticate_user, create_session, validate_session, get_db_connection

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

class TestRBAC(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Obtain tokens for each role
        admin_u = authenticate_user('admin', 'admin123')
        teacher_u = authenticate_user('teacher', 'teacher123')
        accountant_u = authenticate_user('accountant', 'account123')
        student_u = authenticate_user('student10', 'student123')

        cls.tokens = {
            'admin': create_session(admin_u['id'])[0],
            'teacher': create_session(teacher_u['id'])[0],
            'accountant': create_session(accountant_u['id'])[0],
            'student': create_session(student_u['id'])[0]
        }
        cls.student_linked_id = student_u['linked_student_id']

    def test_authentication_success_and_failure(self):
        # Valid login
        code, res = MockRequest("POST", "/api/auth/login", {"username": "admin", "password": "admin123"}).execute()
        self.assertEqual(code, 200)
        self.assertTrue(res["success"])
        self.assertIn("token", res)
        self.assertEqual(res["user"]["role"], "admin")

        # Invalid login
        code, res = MockRequest("POST", "/api/auth/login", {"username": "admin", "password": "wrongpassword"}).execute()
        self.assertEqual(code, 401)
        self.assertIn("error", res)

    def test_unauthenticated_request_blocked(self):
        # Protected endpoint without token should return 401
        code, res = MockRequest("GET", "/api/students").execute()
        self.assertEqual(code, 401)
        self.assertIn("error", res)

    def test_admin_has_full_access(self):
        token = self.tokens['admin']
        # Admin can view students
        code, res = MockRequest("GET", "/api/students", token=token).execute()
        self.assertEqual(code, 200)
        self.assertIsInstance(res, list)

        # Admin can view finance
        code, res = MockRequest("GET", "/api/finance/summary", token=token).execute()
        self.assertEqual(code, 200)
        self.assertIn("total_collected", res)

    def test_teacher_role_restrictions(self):
        token = self.tokens['teacher']
        # Teacher CAN access exams & marks
        code, res = MockRequest("GET", "/api/exams", token=token).execute()
        self.assertEqual(code, 200)

        # Teacher CANNOT access finance summary -> 403 Forbidden
        code, res = MockRequest("GET", "/api/finance/summary", token=token).execute()
        self.assertEqual(code, 403)
        self.assertIn("error", res)

        # Teacher CANNOT collect fee -> 403 Forbidden
        code, res = MockRequest("POST", "/api/finance/pay", {"invoice_id": 1, "amount_paid": 500}, token=token).execute()
        self.assertEqual(code, 403)

    def test_accountant_role_restrictions(self):
        token = self.tokens['accountant']
        # Accountant CAN access finance summary
        code, res = MockRequest("GET", "/api/finance/summary", token=token).execute()
        self.assertEqual(code, 200)

        # Accountant CANNOT enter marks -> 403 Forbidden
        code, res = MockRequest("POST", "/api/marks/bulk", {"exam_id": 1, "subject_id": 1, "marks": []}, token=token).execute()
        self.assertEqual(code, 403)
        self.assertIn("error", res)

    def test_student_role_restrictions_and_self_service(self):
        token = self.tokens['student']
        # Student CAN view their own profile
        code, res = MockRequest("GET", f"/api/students/{self.student_linked_id}", token=token).execute()
        self.assertEqual(code, 200)
        self.assertEqual(res["id"], self.student_linked_id)

        # Student CANNOT view another student's profile -> 403 Forbidden
        other_id = self.student_linked_id + 1
        code, res = MockRequest("GET", f"/api/students/{other_id}", token=token).execute()
        self.assertEqual(code, 403)

        # Student CANNOT view class tabulation ledger -> 403 Forbidden
        code, res = MockRequest("GET", "/api/tabulation?class_id=11&exam_id=2", token=token).execute()
        self.assertEqual(code, 403)

        # Student CANNOT access school finance summary -> 403 Forbidden
        code, res = MockRequest("GET", "/api/finance/summary", token=token).execute()
        self.assertEqual(code, 403)

if __name__ == '__main__':
    unittest.main()
