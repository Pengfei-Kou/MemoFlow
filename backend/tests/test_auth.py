"""
会话鉴权测试：token 签名往返 / 过期 / 篡改 + 登录端点
"""

import time

import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine
from sqlalchemy.pool import StaticPool

import app.database as db_module
from app.config import settings
from app.main import app
from app.services.auth import SESSION_COOKIE, make_session_token, verify_session_token


@pytest.fixture()
def creds(monkeypatch):
    """临时启用鉴权配置（测试环境默认为空）"""
    monkeypatch.setattr(settings, "auth_username", "tester")
    monkeypatch.setattr(settings, "auth_password", "secret-pw")
    yield


@pytest.fixture()
def client():
    """轻量 TestClient（auth 路由不碰业务表，与 test_api 的 fixture 解耦）"""
    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    original_engine = db_module.engine
    db_module.engine = test_engine
    with TestClient(app) as c:
        yield c, test_engine
    db_module.engine = original_engine


class TestSessionToken:
    def test_roundtrip(self, creds):
        token = make_session_token(days=1)
        assert verify_session_token(token)

    def test_expired(self, creds):
        exp = int(time.time()) - 10
        from app.services.auth import _sign
        assert not verify_session_token(f"{exp}.{_sign(exp)}")

    def test_tampered_signature(self, creds):
        token = make_session_token(days=1)
        exp, sig = token.split(".", 1)
        bad = f"{exp}.{'0' * len(sig)}"
        assert not verify_session_token(bad)

    def test_garbage(self, creds):
        assert not verify_session_token("not-a-token")
        assert not verify_session_token("")

    def test_password_rotation_invalidates(self, creds, monkeypatch):
        token = make_session_token(days=1)
        monkeypatch.setattr(settings, "auth_password", "rotated")
        assert not verify_session_token(token)


class TestLoginAPI:
    def test_login_success_sets_cookie(self, client, creds):
        c, _ = client
        resp = c.post("/api/auth/login", json={
            "username": "tester", "password": "secret-pw", "remember": True,
        })
        assert resp.status_code == 200
        assert SESSION_COOKIE in resp.cookies
        assert verify_session_token(resp.cookies[SESSION_COOKIE])

    def test_login_wrong_password(self, client, creds):
        c, _ = client
        resp = c.post("/api/auth/login", json={
            "username": "tester", "password": "wrong",
        })
        assert resp.status_code == 401

    def test_login_when_auth_disabled(self, client):
        c, _ = client
        resp = c.post("/api/auth/login", json={"username": "a", "password": "b"})
        assert resp.status_code == 400

    def test_logout_clears_cookie(self, client, creds):
        c, _ = client
        c.post("/api/auth/login", json={"username": "tester", "password": "secret-pw"})
        resp = c.post("/api/auth/logout")
        assert resp.status_code == 200
