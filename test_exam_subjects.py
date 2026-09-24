"""
test_exam_subjects.py - Tests for CDC subjects across all 17 classes, public access, and subject/exam creation
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

class ExamSubjectsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        admin_u = authenticate_user('admin', 'admin123')
        cls.admin_token, _ = create_session(admin_u['id'])

        teacher_u = authenticate_user('teacher', 'teacher123')
        cls.teacher_token, _ = create_session(teacher_u['id'])

        student_u = authenticate_user('student10', 'student123')
        cls.student_token, _ = create_session(student_u['id'])

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

        status_code = [200]
        def mock_send_response(code, message=None):
            status_code[0] = code
        def mock_send_header(k, v):
            pass
        def mock_end_headers():
            pass

        handler.send_response = mock_send_response
        handler.send_header = mock_send_header
        handler.end_headers = mock_end_headers

        if method == "GET":
            handler.do_GET()
        elif method == "POST":
            handler.do_POST()

        handler.wfile.seek(0)
        return status_code[0], handler.wfile.read()

    def test_public_catalog_endpoints(self):
        """Classes, Sections, Subjects, and Exams must be accessible without authentication."""
        for path in ["/api/classes", "/api/sections", "/api/subjects", "/api/exams"]:
            status, body = self.run_handler("GET", path, token=None)
            self.assertEqual(status, 200, f"Failed for {path}")
            data = json.loads(body.decode("utf-8"))
            self.assertIsInstance(data, list)
            self.assertGreater(len(data), 0, f"Expected non-empty list for {path}")

    def test_all_17_classes_have_subjects(self):
        """Every single class from ECD to Class 12 must have CDC curriculum subjects."""
        status, body = self.run_handler("GET", "/api/classes")
        self.assertEqual(status, 200)
        classes = json.loads(body.decode("utf-8"))
        self.assertEqual(len(classes), 17, "Expected exactly 17 classes from ECD to Class 12")

        for c in classes:
            status, sub_body = self.run_handler("GET", f"/api/subjects?class_id={c['id']}")
            self.assertEqual(status, 200)
            subs = json.loads(sub_body.decode("utf-8"))
            self.assertGreater(
                len(subs), 0,
                f"Class {c['name']} (ID: {c['id']}) has 0 subjects! Must have CDC subjects."
            )

    def test_create_exam_term(self):
        """Creating an exam term works with teacher or admin credentials."""
        exam_payload = {
            "name": "Third Terminal Assessment 2081",
            "term": "Third Term",
            "academic_year": "2081",
            "is_published": 1
        }
        status, body = self.run_handler("POST", "/api/exams", body=exam_payload, token=self.teacher_token)
        self.assertEqual(status, 200)
        res = json.loads(body.decode("utf-8"))
        self.assertTrue(res.get("success"))
        self.assertIn("id", res)

    def test_add_subject_authorized(self):
        """Admin and Teacher can add new subjects."""
        status, body = self.run_handler("GET", "/api/classes")
        classes = json.loads(body.decode("utf-8"))
        c10 = next(c for c in classes if c['name'] == 'Class 10')

        subject_payload = {
            "class_id": c10['id'],
            "code": "Opt.108",
            "name_en": "Agriculture and Organic Farming",
            "name_np": "कृषि तथा जैविक खेती",
            "credit_hours": 4.0,
            "theory_full_marks": 50.0,
            "theory_pass_marks": 18.0,
            "practical_full_marks": 50.0,
            "practical_pass_marks": 20.0,
            "is_optional": 1
        }
        status, body = self.run_handler("POST", "/api/subjects", body=subject_payload, token=self.admin_token)
        self.assertEqual(status, 200)
        res = json.loads(body.decode("utf-8"))
        self.assertTrue(res.get("success"))
        self.assertIn("id", res)

    def test_add_subject_forbidden_for_student(self):
        """Students cannot add subjects."""
        subject_payload = {
            "class_id": 1,
            "code": "Fake.001",
            "name_en": "Hacking 101"
        }
        status, _ = self.run_handler("POST", "/api/subjects", body=subject_payload, token=self.student_token)
        self.assertEqual(status, 403)

if __name__ == '__main__':
    unittest.main()
