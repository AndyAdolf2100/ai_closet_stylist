import base64
import os
from pathlib import Path
from typing import Literal

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from pydantic import Field

from .errors import StylistError
from .models import Model
from .upstream import Upstream


class LoginRequest(Model):
    mobile: str = Field(pattern=r"^1[3-9]\d{9}$")
    code: str = Field(pattern=r"^\d{4,8}$")
    device_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")


class GenderLoginRequest(Model):
    token: str = Field(min_length=1, max_length=8192, repr=False)
    sex: Literal[1, 2]
    device_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")


async def completed_session(settings, data):
    token_data = data["token"]
    token = token_data["access_token"]
    if not isinstance(token, str) or not token.strip():
        raise KeyError("access_token")
    upstream = Upstream(settings, "Bearer " + token)
    owner = await upstream.identity()
    return {"access_token": token, "access_token_expires_at": token_data.get("access_token_expires_at"),
            "user": {"id": owner}}


async def finish_gender_login(settings, request):
    if os.getenv("STYLIST_ENV") == "production" and not settings.allow_mobile_login:
        raise StylistError("local_login_disabled", "生产环境请使用 App 已验证的登录态。", 404)
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            response = await client.post(settings.server_url + "/users/app/login/set/sex",
                headers={"version": settings.login_app_version, "device": "PC", "Device-Id": request.device_id},
                json={"token": request.token, "sex": request.sex})
            response.raise_for_status()
            payload = response.json()
        if payload.get("code") != 0:
            raise StylistError("gender_login_rejected", "性别确认未成功，请重试；登录凭证过期时请重新登录。", 401)
        return await completed_session(settings, payload["data"])
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise StylistError("gender_login_unknown", "登录完成结果暂未确认，请重新登录后继续；不会显示为已保存。", 502) from None


async def login(settings, request):
    if os.getenv("STYLIST_ENV") == "production" and not settings.allow_mobile_login:
        raise StylistError("local_login_disabled", "生产环境请使用 App 已验证的登录态。", 404)
    try:
        key = serialization.load_pem_public_key(Path(settings.login_public_key).read_bytes())
        mobile = base64.b64encode(key.encrypt(request.mobile.encode(), padding.PKCS1v15())).decode()
    except (OSError, ValueError, TypeError, AttributeError):
        raise StylistError("login_not_configured", "请配置现有服务的手机号登录公钥。") from None
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            response = await client.post(settings.server_url + "/users/app/login/mobile/code",
                headers={"version": settings.login_app_version, "device": "PC", "Device-Id": request.device_id},
                json={"mobile": mobile, "code": request.code, "device_id": request.device_id})
            response.raise_for_status()
            payload = response.json()
        if payload.get("code") != 0:
            raise StylistError("login_rejected", "登录失败，请核对手机号与验证码。", 401)
        data = payload["data"]
        if data.get("sex_token"):
            # No account write here: the final onboarding action submits the choice.
            info = data.get("user_info") or {}
            return {"requires_gender": True, "sex_token": data["sex_token"],
                    "user": {"user_name": info.get("nick_name", data.get("nick_name", "")) or "",
                             "user_gender": {1: "男", 2: "女"}.get(info.get("sex"))}}
        return await completed_session(settings, data)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise StylistError("login_unavailable", "登录服务响应异常，请稍后重试。") from None
