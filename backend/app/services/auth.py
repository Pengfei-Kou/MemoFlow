"""
会话鉴权：HMAC 签名的长效会话 token（配合登录页的"记住我"）

- token 格式：`<过期时间戳>.<hmac_sha256_hex>`，签名内容 = "username|exp"
- 签名密钥由 AUTH_USERNAME/AUTH_PASSWORD 派生：轮换密码即让所有已发会话失效，
  无需额外管理一个 session secret
- Basic Auth 仍然并行有效（TG 提醒等脚本在用），见 main.py 中间件
"""

import hashlib
import hmac
import time

from app.config import settings

SESSION_COOKIE = "memoflow_session"


def _secret() -> bytes:
    raw = f"memoflow-session:{settings.auth_username}:{settings.auth_password}"
    return hashlib.sha256(raw.encode()).digest()


def _sign(exp: int) -> str:
    payload = f"{settings.auth_username}|{exp}".encode()
    return hmac.new(_secret(), payload, hashlib.sha256).hexdigest()


def make_session_token(days: int) -> str:
    exp = int(time.time()) + days * 86400
    return f"{exp}.{_sign(exp)}"


def verify_session_token(token: str) -> bool:
    try:
        exp_str, sig = token.split(".", 1)
        exp = int(exp_str)
    except ValueError:
        return False
    if exp < time.time():
        return False
    return hmac.compare_digest(sig, _sign(exp))
