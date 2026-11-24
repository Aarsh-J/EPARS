import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware

from modules.auth import (
    AuthenticationMiddleware,
    hash_password,
    router as auth_router,
)


class AuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = "local-test-password"
        cls.password_hash = hash_password(cls.password)

    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "ADMIN_USERNAME": "test-admin",
                "ADMIN_PASSWORD_HASH": self.password_hash,
                "SESSION_SECRET_KEY": "test-session-secret-key-that-is-long-enough",
                "AUTH_COOKIE_SECURE": "false",
                "AUTH_COOKIE_SAMESITE": "lax",
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

        app = FastAPI()
        app.add_middleware(AuthenticationMiddleware)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        app.include_router(auth_router, prefix="/api/auth")

        @app.get("/api/private/read")
        def private_read():
            return {"value": "protected"}

        @app.post("/api/private/write")
        def private_write():
            return {"saved": True}

        @app.get("/health")
        def health():
            return {"status": "ok"}

        self.client = TestClient(app)

    def test_anonymous_reads_and_writes_are_rejected(self):
        self.assertEqual(self.client.get("/api/private/read").status_code, 401)
        self.assertEqual(self.client.post("/api/private/write").status_code, 401)
        self.assertEqual(self.client.get("/health").status_code, 200)

    def test_cors_preflight_is_not_blocked_by_authentication(self):
        response = self.client.options(
            "/api/private/write",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-csrf-token",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"], "http://localhost:5173"
        )

    def test_login_protects_writes_with_csrf_and_logout_clears_session(self):
        response = self.client.post(
            "/api/auth/login",
            json={"username": "test-admin", "password": self.password},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["role"], "admin")
        self.assertIn("httponly", response.headers["set-cookie"].lower())
        self.assertEqual(self.client.get("/api/private/read").status_code, 200)
        self.assertEqual(self.client.post("/api/private/write").status_code, 403)

        csrf_token = self.client.cookies["epars_csrf"]
        response = self.client.post(
            "/api/private/write", headers={"X-CSRF-Token": csrf_token}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me").json()["username"], "test-admin")

        self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
        self.assertEqual(self.client.get("/api/private/read").status_code, 401)

    def test_invalid_credentials_are_rejected(self):
        response = self.client.post(
            "/api/auth/login",
            json={"username": "test-admin", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 401)

    def test_missing_auth_configuration_fails_closed(self):
        with patch.dict(os.environ, {"SESSION_SECRET_KEY": ""}):
            response = self.client.get("/api/private/read")
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
