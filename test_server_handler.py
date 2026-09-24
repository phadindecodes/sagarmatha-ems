"""
test_server_handler.py - In-process test of EMSRequestHandler endpoints with authentication
"""

import io
import json
import unittest
from app import EMSRequestHandler
from database import authenticate_user, create_session, get_db_connection

class MockSocket:
    def __init__(self, data=b""):
        self.data = data
        self.output = io.BytesIO()

    def makefile(self, mode, *args, **kwargs):
        if 'r' in mode:
            return io.BytesIO(self.data)
        elif 'w' in mode or 'b' in mode:
            return self.output

class MockRequest:
    def __init__(self, method="GET", path="/", body=b"", token=None):
        req_lines = [f"{method} {path} HTTP/1.1", "Host: localhost:8000"]
        if body:
            req_lines.append(f"Content-Length: {len(body)}")
            req_lines.append("Content-Type: application/json")
        if token:
            req_lines.append(f"Authorization: Bearer {token}")
        req_lines.append("")
        req_lines.append("")
        raw_req = "\r\n".join(req_lines).encode("utf-8") + body
        self.sock = MockSocket(raw_req)

class HandlerTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        admin_u = authenticate_user('admin', 'admin123')
        cls.token, _ = create_session(admin_u['id'])

    def run_handler(self, method="GET", path="/", body=None, token=None):
        body_bytes = json.dumps(body).encode("utf-8") if body else b""
        req = MockRequest(method, path, body_bytes, token)
        handler = EMSRequestHandler.__new__(EMSRequestHandler)
        handler.rfile = io.BytesIO(body_bytes)
        handler.wfile = io.BytesIO()
        handler.path = path
        handler.command = method
        headers = {
            "Content-Length": str(len(body_bytes)),
            "Content-Type": "application/json"
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        handler.headers = headers
        handler.request_version = "HTTP/1.1"

        captured_headers = {}
        status_code = [200]

        def mock_send_response(code, message=None):
            status_code[0] = code
        def mock_send_header(k, v):
            captured_headers[k] = v
        def mock_end_headers():
            pass

        handler.send_response = mock_send_response
        handler.send_header = mock_send_header
        handler.end_headers = mock_end_headers

        if method == "GET":
            handler.do_GET()
        elif method == "POST":
            handler.do_POST()
        elif method == "PUT":
            handler.do_PUT()

        handler.wfile.seek(0)
        out_bytes = handler.wfile.read()
        return status_code[0], captured_headers, out_bytes

    def test_api_info_public(self):
        # Public endpoint requires no token
        status, headers, body = self.run_handler("GET", "/api/info")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("Shree Sagarmatha Secondary School", data["name_en"])
        self.assertEqual(data["established_bs"], 2034)

    def test_api_students_authenticated(self):
        # Authenticated with token
        status, headers, body = self.run_handler("GET", "/api/students", token=self.token)
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_api_students_unauthenticated_blocked(self):
        # Unauthenticated request -> 401
        status, headers, body = self.run_handler("GET", "/api/students")
        self.assertEqual(status, 401)

    def test_api_gradesheet(self):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM students WHERE reg_no = 'SSS-2081-1001';")
        st_id = cur.fetchone()['id']
        cur.execute("SELECT id FROM exams WHERE term = 'Second Term';")
        ex_id = cur.fetchone()['id']
        conn.close()

        status, headers, body = self.run_handler("GET", f"/api/gradesheet?student_id={st_id}&exam_id={ex_id}", token=self.token)
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("school", data)
        self.assertIn("student", data)
        self.assertIn("subjects", data)
        self.assertIn("summary", data)

    def test_api_tabulation(self):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM classes WHERE name = 'Class 10';")
        c_id = cur.fetchone()['id']
        cur.execute("SELECT id FROM exams WHERE term = 'Second Term';")
        ex_id = cur.fetchone()['id']
        conn.close()

        status, headers, body = self.run_handler("GET", f"/api/tabulation?class_id={c_id}&exam_id={ex_id}", token=self.token)
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("students", data)
        self.assertIn("subjects", data)

    def test_api_finance_summary(self):
        status, headers, body = self.run_handler("GET", "/api/finance/summary", token=self.token)
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("total_collected", data)

    def test_api_finance_receipt(self):
        status, headers, body = self.run_handler("GET", "/api/finance/receipt/REC-2081-1001", token=self.token)
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["receipt_no"], "REC-2081-1001")

    def test_post_admission_inquiry_public(self):
        inq_payload = {
            "applicant_name": "Sujan Kafle",
            "applying_class": "Class 11 Science",
            "guardian_name": "Gita Kafle",
            "phone": "9842112233",
            "address": "Bhadrapur-2",
            "previous_school": "Sagarmatha School",
            "message": "Computer science stream inquiry"
        }
        status, headers, body = self.run_handler("POST", "/api/inquiries", inq_payload)
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])

if __name__ == "__main__":
    unittest.main()
