"""
test_gallery_and_password.py - Tests for Photo Gallery and Password Change functionality
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

class GalleryAndPasswordTest(unittest.TestCase):

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

    def test_public_gallery_accessible(self):
        """Gallery must be public without requiring login."""
        status, body = self.run_handler("GET", "/api/gallery")
        self.assertEqual(status, 200)
        photos = json.loads(body.decode("utf-8"))
        self.assertIsInstance(photos, list)
        self.assertGreaterEqual(len(photos), 8)
        self.assertIn("image_url", photos[0])
        self.assertIn("title", photos[0])

    def test_gallery_category_filtering(self):
        """Gallery can filter by category."""
        status, body = self.run_handler("GET", "/api/gallery?category=Sports")
        self.assertEqual(status, 200)
        photos = json.loads(body.decode("utf-8"))
        self.assertGreater(len(photos), 0)
        for p in photos:
            self.assertEqual(p["category"], "Sports")

    def test_change_password_unauthenticated(self):
        """Unauthenticated password change must be rejected with 401."""
        status, _ = self.run_handler("POST", "/api/auth/change-password", body={
            "current_password": "any",
            "new_password": "newpassword123"
        })
        self.assertEqual(status, 401)

    def test_change_password_wrong_current(self):
        """Changing password with wrong current password must return 400."""
        user = authenticate_user('accountant', 'account123')
        self.assertIsNotNone(user)
        token, _ = create_session(user['id'])

        status, body = self.run_handler("POST", "/api/auth/change-password", body={
            "current_password": "wrongpassword!",
            "new_password": "brandnewpassword123"
        }, token=token)
        self.assertEqual(status, 400)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("Current password", data.get("error", ""))

    def test_change_password_too_short(self):
        """New password shorter than 6 characters must be rejected."""
        user = authenticate_user('accountant', 'account123')
        token, _ = create_session(user['id'])

        status, body = self.run_handler("POST", "/api/auth/change-password", body={
            "current_password": "account123",
            "new_password": "123"
        }, token=token)
        self.assertEqual(status, 400)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("at least 6 characters", data.get("error", ""))

    def test_change_password_success_and_login_verification(self):
        """Changing password successfully and testing login with new password."""
        # Use student10 for testing password change
        student_user = authenticate_user('student10', 'student123')
        self.assertIsNotNone(student_user)
        token, _ = create_session(student_user['id'])

        # Change to new password
        status, body = self.run_handler("POST", "/api/auth/change-password", body={
            "current_password": "student123",
            "new_password": "mypassword456"
        }, token=token)
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data.get("success"))

        # Old password should now fail
        old_auth = authenticate_user('student10', 'student123')
        self.assertIsNone(old_auth)

        # New password should succeed
        new_auth = authenticate_user('student10', 'mypassword456')
        self.assertIsNotNone(new_auth)

        # Revert back to original password for demo account stability
        token2, _ = create_session(new_auth['id'])
        status, _ = self.run_handler("POST", "/api/auth/change-password", body={
            "current_password": "mypassword456",
            "new_password": "student123"
        }, token=token2)
        self.assertEqual(status, 200)
        reverted_auth = authenticate_user('student10', 'student123')
        self.assertIsNotNone(reverted_auth)

if __name__ == '__main__':
    unittest.main()
