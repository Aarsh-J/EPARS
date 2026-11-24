import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Protocol

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

SESSION_COOKIE = "epars_session"
CSRF_COOKIE = "epars_csrf"
CSRF_HEADER = "X-CSRF-Token"
SESSION_TTL_SECONDS = 30 * 60
PASSWORD_HASH_ITERATIONS = 600_000
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class AuthConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthSettings:
    username: str
    password_hash: str
    secret_key: str
    cookie_secure: bool
    cookie_samesite: str


@dataclass(frozen=True)
class Principal:
    user_id: str
    username: str
    role: str


class AuthProvider(Protocol):
    def authenticate(self, username: str, password: str) -> Principal | None: ...

    def get_user(self, user_id: str) -> Principal | None: ...


def load_auth_settings() -> AuthSettings:
    username = os.getenv("ADMIN_USERNAME", "").strip()
    password_hash = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
    secret_key = os.getenv("SESSION_SECRET_KEY", "")
    cookie_secure_value = os.getenv("AUTH_COOKIE_SECURE", "true").strip().lower()
    cookie_samesite = os.getenv("AUTH_COOKIE_SAMESITE", "lax").strip().lower()

    if not username or not password_hash or not secret_key:
        raise AuthConfigurationError(
            "Set ADMIN_USERNAME, ADMIN_PASSWORD_HASH, and SESSION_SECRET_KEY."
        )
    if len(secret_key) < 32:
        raise AuthConfigurationError("SESSION_SECRET_KEY must be at least 32 characters.")
    if cookie_secure_value not in {"true", "false"}:
        raise AuthConfigurationError("AUTH_COOKIE_SECURE must be true or false.")
    if cookie_samesite not in {"lax", "strict", "none"}:
        raise AuthConfigurationError("AUTH_COOKIE_SAMESITE must be lax, strict, or none.")
    if cookie_samesite == "none" and cookie_secure_value != "true":
        raise AuthConfigurationError("AUTH_COOKIE_SECURE must be true when SameSite is none.")

    _parse_password_hash(password_hash)
    return AuthSettings(
        username=username,
        password_hash=password_hash,
        secret_key=secret_key,
        cookie_secure=cookie_secure_value == "true",
        cookie_samesite=cookie_samesite,
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS
    )
    salt_text = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt_text}${digest.hex()}"


def _parse_password_hash(password_hash: str) -> tuple[int, bytes, bytes]:
    try:
        algorithm, rounds_text, salt_text, digest_text = password_hash.split("$")
        rounds = int(rounds_text)
        salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
        digest = bytes.fromhex(digest_text)
    except (ValueError, TypeError) as error:
        raise AuthConfigurationError("ADMIN_PASSWORD_HASH is not a valid password hash.") from error

    if (
        algorithm != "pbkdf2_sha256"
        or not 100_000 <= rounds <= 5_000_000
        or len(salt) < 16
        or len(digest) != hashlib.sha256().digest_size
    ):
        raise AuthConfigurationError("ADMIN_PASSWORD_HASH is not a valid password hash.")
    return rounds, salt, digest


def _verify_password(password: str, password_hash: str) -> bool:
    rounds, salt, expected_digest = _parse_password_hash(password_hash)
    actual_digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, rounds
    )
    return hmac.compare_digest(actual_digest, expected_digest)


class EnvironmentAuthProvider:
    def __init__(self, settings: AuthSettings):
        self._settings = settings

    def authenticate(self, username: str, password: str) -> Principal | None:
        password_matches = _verify_password(password, self._settings.password_hash)
        username_matches = hmac.compare_digest(
            username.encode("utf-8"), self._settings.username.encode("utf-8")
        )
        if not username_matches or not password_matches:
            return None
        return self.get_user(self._settings.username)

    def get_user(self, user_id: str) -> Principal | None:
        if not hmac.compare_digest(
            user_id.encode("utf-8"), self._settings.username.encode("utf-8")
        ):
            return None
        return Principal(user_id=user_id, username=user_id, role="admin")


def build_auth_provider(settings: AuthSettings) -> AuthProvider:
    return EnvironmentAuthProvider(settings)


def _encode_segment(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_segment(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign(payload_segment: str, secret_key: str) -> str:
    signature = hmac.new(
        secret_key.encode("utf-8"), payload_segment.encode("ascii"), hashlib.sha256
    ).digest()
    return _encode_segment(signature)


def _create_session_token(principal: Principal, csrf_token: str, secret_key: str) -> str:
    payload = {
        "sub": principal.user_id,
        "exp": int(time.time()) + SESSION_TTL_SECONDS,
        "csrf": csrf_token,
    }
    payload_segment = _encode_segment(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    return f"{payload_segment}.{_sign(payload_segment, secret_key)}"


def _read_session_token(token: str, secret_key: str) -> dict | None:
    if len(token) > 4096 or token.count(".") != 1:
        return None
    payload_segment, supplied_signature = token.split(".", 1)
    expected_signature = _sign(payload_segment, secret_key)
    if not hmac.compare_digest(supplied_signature, expected_signature):
        return None

    try:
        payload = json.loads(_decode_segment(payload_segment))
    except (ValueError, TypeError):
        return None
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("sub"), str)
        or not isinstance(payload.get("csrf"), str)
        or not isinstance(payload.get("exp"), int)
        or payload["exp"] <= int(time.time())
    ):
        return None
    return payload


def _set_auth_cookies(
    response: Response, settings: AuthSettings, principal: Principal
) -> None:
    csrf_token = secrets.token_urlsafe(32)
    token = _create_session_token(principal, csrf_token, settings.secret_key)
    cookie_options = {
        "max_age": SESSION_TTL_SECONDS,
        "path": "/",
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
    }
    response.set_cookie(SESSION_COOKIE, token, httponly=True, **cookie_options)
    response.set_cookie(CSRF_COOKIE, csrf_token, httponly=False, **cookie_options)


router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(credentials: LoginRequest, response: Response):
    try:
        settings = load_auth_settings()
    except AuthConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    principal = build_auth_provider(settings).authenticate(
        credentials.username, credentials.password
    )
    if principal is None:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    _set_auth_cookies(response, settings, principal)
    return {
        "user": {
            "id": principal.user_id,
            "username": principal.username,
            "role": principal.role,
        }
    }


@router.post("/logout")
def logout(response: Response):
    for cookie_name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(cookie_name, path="/", samesite="lax")
    return {"ok": True}


@router.get("/me")
def current_user(request: Request):
    principal = getattr(request.state, "user", None)
    if principal is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return {
        "id": principal.user_id,
        "username": principal.username,
        "role": principal.role,
    }


class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path in {
            "/health",
            "/api/auth/login",
            "/api/auth/logout",
        }:
            return await call_next(request)

        try:
            settings = load_auth_settings()
        except AuthConfigurationError as error:
            return JSONResponse(status_code=503, content={"detail": str(error)})

        token = request.cookies.get(SESSION_COOKIE)
        claims = _read_session_token(token, settings.secret_key) if token else None
        if claims is None:
            return JSONResponse(
                status_code=401, content={"detail": "Authentication required."}
            )

        principal = build_auth_provider(settings).get_user(claims["sub"])
        if principal is None:
            return JSONResponse(
                status_code=401, content={"detail": "Authentication required."}
            )

        if request.method not in SAFE_METHODS:
            csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
            csrf_header = request.headers.get(CSRF_HEADER, "")
            session_csrf = claims["csrf"]
            if not (
                hmac.compare_digest(csrf_cookie, session_csrf)
                and hmac.compare_digest(csrf_header, session_csrf)
            ):
                return JSONResponse(
                    status_code=403, content={"detail": "Invalid CSRF token."}
                )

        request.state.user = principal
        return await call_next(request)
