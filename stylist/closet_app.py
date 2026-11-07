"""Fixed App presentation and explicit feedback boundary; separate from Agent tools."""
import base64
import binascii
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Header, Query, Response
from pydantic import BaseModel, Field, field_validator

from .errors import AuthenticationExpired, StylistError
from .points import available_points
from .upstream import _business_payload

READ_PAGES = {
    "fitting-records": "/api/generation_records/list",
    "trend-records": "/api/generation_records/list",
    "my-outfits": "/api/ai_outfit_merge_my_outfit/list",
    "orders": "/api/vip_orders/list",
    "points-orders": "/api/booster/order_list",
    "messages": "/api/message/list",
    "profile": "/api/user/info",
    "memories": "/api/memories",
    "album": "/api/home/outfit_album",
    "recent": "/api/user_product/last_add_product",
    "categories": "/api/user_product/show_list",
    "closets": "/api/wardrobes/list",
    "inspiration": "/api/system_commended_outfit/list",
}


class FeedbackBody(BaseModel):
    content: str = Field(min_length=1, max_length=300)
    urls: list[str] = Field(default_factory=list, max_length=9)

    @field_validator("content")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("反馈内容不能为空")
        return value.strip()

    @field_validator("urls")
    @classmethod
    def image_urls(cls, values):
        if any(not url.startswith("https://") or len(url) > 2048 for url in values):
            raise ValueError("图片地址无效")
        return values


class FeedbackImage(BaseModel):
    image_url: str = Field(max_length=7_000_000)

    @field_validator("image_url")
    @classmethod
    def valid_image(cls, value):
        if not value.startswith(("data:image/jpeg;base64,", "data:image/png;base64,")):
            raise ValueError("请选择JPEG或PNG图片")
        try:
            raw = base64.b64decode(value.split(",", 1)[1], validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("图片内容无效") from exc
        if not raw or len(raw) > 5 * 1024 * 1024:
            raise ValueError("图片应不大于5MB")
        return value


def router(settings):
    routes = APIRouter(prefix="/stylist-api/app")

    async def fixed_request(method, path, authorization, **kwargs):
        if not authorization or not authorization.startswith("Bearer ") or not authorization[7:].strip():
            raise AuthenticationExpired()
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout, trust_env=False,
                                         follow_redirects=False) as client:
                result = await client.request(method, settings.server_url + path, headers={
                    "Authorization": authorization, "version": settings.login_app_version, "device": "PC"}, **kwargs)
                return _business_payload(result)
        except (httpx.HTTPError, ValueError) as exc:
            raise StylistError("app_request_unconfirmed", "操作结果暂未确认，请稍后重试。", 502) from exc

    @routes.get("/purchase/{section}")
    async def purchase_catalog(section: str, response: Response, authorization: str | None = Header(default=None)):
        # A fixed read-only boundary, not a general Server proxy. Eligibility stays on Server.
        paths = {"member": "/api/vip_product/products",
                 "benefits": "/api/vip_product/privileges/compare",
                 "points": "/api/booster/products", "config": "/api/app_config/config_check"}
        if section not in paths:
            raise StylistError("purchase_section_missing", "没有这个商品分类。", 404)
        response.headers["Cache-Control"] = "no-store"
        data = await fixed_request("GET", paths[section], authorization)
        key = {"member": "products", "points": "list", "benefits": "benefit_table"}.get(section)
        expected = dict if section == "benefits" else list
        if not isinstance(data, dict) or (key and not isinstance(data.get(key), expected)):
            raise StylistError("purchase_contract_error", "商品资料格式异常，请重新读取。", 502)
        if section == "config":
            # Public purchase display fields only; do not expose unrelated app configuration.
            data = {k: data[k] for k in ("vip_tip", "prettify_cost", "fitting_cost") if k in data}
            origin = urlsplit(settings.purchase_web_url)
            if origin.scheme == "https" and origin.netloc and not origin.username and not origin.password:
                base = settings.purchase_web_url.rstrip("/")
                data["agreements"] = {"member": base + "/membershipService",
                                      "subscription": base + "/continuousSubscription",
                                      "points": base + "/pointsPurchase"}
        return {"data": data}

    @routes.get("/points")
    async def points_balance(response: Response, authorization: str | None = Header(default=None)):
        response.headers["Cache-Control"] = "no-store"
        data = await fixed_request("GET", "/api/vip_center/points_detail", authorization)
        return {"data": {"total_available": available_points(data)}}

    @routes.get("/checkin")
    async def checkin_status(response: Response, authorization: str | None = Header(default=None)):
        response.headers["Cache-Control"] = "no-store"
        today = await fixed_request("GET", "/api/check_in/today", authorization)
        recent = await fixed_request("GET", "/api/check_in/recent", authorization)
        if not isinstance(today, dict) or not isinstance(today.get("signed"), bool) or not isinstance(recent, dict) or not isinstance(recent.get("days"), list):
            raise StylistError("checkin_contract_error", "签到状态格式异常，请稍后重试。", 502)
        # Config is independent: failure must not turn a known signed state into unsigned.
        points = None
        try:
            config = await fixed_request("GET", "/api/app_config/config_check", authorization)
            value = config.get("daily_checkin_points") if isinstance(config, dict) else None
            if type(value) is int and value >= 0:
                points = value
        except StylistError:
            pass
        return {"data": {**today, "days": recent["days"], "tips": recent.get("tips", ""), "daily_points": points}}

    @routes.get("/milestones")
    async def points_milestones(response: Response, authorization: str | None = Header(default=None)):
        response.headers["Cache-Control"] = "no-store"
        data = await fixed_request("GET", "/api/milestones", authorization)
        valid = isinstance(data, dict) and type(data.get("current_item_count")) is int and data["current_item_count"] >= 0
        tiers = data.get("tiers") if isinstance(data, dict) else None
        if (not valid or not isinstance(tiers, list) or len(tiers) > 20 or any(
                not isinstance(t, dict) or any(type(t.get(k)) is not int for k in ("level", "threshold", "reward"))
                or t["level"] < 1 or t["threshold"] < 1 or t["reward"] < 0 or type(t.get("granted")) is not bool
                for t in tiers) or len({t["level"] for t in tiers}) != len(tiers)):
            raise StylistError("milestones_contract_error", "衣橱任务状态暂未确认，请稍后重试。", 502)
        return {"data": {"current_item_count": data["current_item_count"],
                         "tiers": sorted(tiers, key=lambda t: t["threshold"])}}

    @routes.post("/checkin")
    async def claim_checkin(response: Response, authorization: str | None = Header(default=None)):
        response.headers["Cache-Control"] = "no-store"
        result = await fixed_request("POST", "/api/check_in", authorization)
        if not isinstance(result, dict) or not isinstance(result.get("granted"), bool) or type(result.get("points_added")) is not int or result["points_added"] < 0:
            raise StylistError("checkin_unconfirmed", "签到回执暂未确认，请刷新状态后再查看。", 502)
        return {"data": result}

    @routes.post("/feedback")
    async def submit_feedback(body: FeedbackBody, response: Response,
                              authorization: str | None = Header(default=None)):
        response.headers["Cache-Control"] = "no-store"
        data = await fixed_request("POST", "/api/feedback/add", authorization, json=body.model_dump())
        return {"data": data}

    @routes.post("/feedback-image")
    async def upload_feedback_image(body: FeedbackImage, response: Response,
                                    authorization: str | None = Header(default=None)):
        response.headers["Cache-Control"] = "no-store"
        data = await fixed_request("POST", "/api/upload/base64/image", authorization,
                                   json={"upload_type": "feedback", "image_url": body.image_url})
        return {"data": data}

    @routes.post("/avatar")
    async def replace_avatar(body: FeedbackImage, response: Response,
                             authorization: str | None = Header(default=None)):
        # Same multipart account endpoint as iOS; never a wardrobe/twin write.
        from .media import image_digest
        image_digest(body.image_url)
        mime = body.image_url.split(";", 1)[0].removeprefix("data:")
        raw = base64.b64decode(body.image_url.split(",", 1)[1], validate=True)
        data = await fixed_request("POST", "/users/user/modify/avatar_url", authorization,
                                   data={"upload_type": "personal"},
                                   files={"file": ("avatar.png" if mime == "image/png" else "avatar.jpg", raw, mime)})
        url = (data.get("url") or data.get("image_url")) if isinstance(data, dict) else None
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            raise StylistError("avatar_unconfirmed", "头像保存结果暂未确认，请重新查看账号资料。", 502)
        response.headers["Cache-Control"] = "no-store"
        return {"data": {"image_url": url}}

    @routes.get("/message-detail/{message_id}")
    async def message_detail(message_id: int, response: Response,
                             authorization: str | None = Header(default=None)):
        if message_id <= 0:
            raise StylistError("invalid_message", "消息标识无效。", 400)
        response.headers["Cache-Control"] = "no-store"
        data = await fixed_request("GET", "/api/message/detail", authorization, params={"id": message_id})
        if not isinstance(data, dict) or data.get("id") != message_id:
            raise StylistError("app_page_contract_error", "消息数据格式异常。", 502)
        return {"data": data}

    @routes.get("/{section}")
    async def read_page(section: str, response: Response,
                        page: int = Query(default=1, ge=1, le=1000),
                        outfit_id: int = Query(default=0, ge=0),
                        outfit_id_type: int = Query(default=0, ge=0),
                        authorization: str | None = Header(default=None)):
        if section not in READ_PAGES:
            raise StylistError("endpoint_not_allowed", "该页面暂未接入。", 404)
        if not authorization or not authorization.startswith("Bearer ") or not authorization[7:].strip():
            raise AuthenticationExpired()
        response.headers["Cache-Control"] = "no-store"
        params = {"page": page, "page_size": 10}
        if section in {"fitting-records", "trend-records"}:
            params["type"] = "fitting" if section == "fitting-records" else "trend"
        if section == "my-outfits":
            params = {"outfit_id": outfit_id, "outfit_id_type": outfit_id_type}
        if section == "inspiration":
            params["source"] = 1
        if section == "closets":
            params["type"] = 0
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout, trust_env=False,
                                         follow_redirects=False) as client:
                result = await client.get(settings.server_url + READ_PAGES[section],
                    params=params if section in {"album", "closets", "inspiration", "messages", "orders", "points-orders", "fitting-records", "trend-records", "my-outfits"} else None,
                    headers={"Authorization": authorization, "version": settings.login_app_version, "device": "PC"})
                data = _business_payload(result)
                if section == "messages" and isinstance(data, list):
                    data = {"list": data}
                list_key = "items" if section in {"album", "memories"} else "list"
                if not isinstance(data, dict) or (section != "profile" and not isinstance(data.get(list_key), list)):
                    raise StylistError("app_page_contract_error", "页面数据格式异常，请稍后重试。", 502)
                return {"data": data}
        except (httpx.HTTPError, ValueError) as exc:
            raise StylistError("app_page_unavailable", "暂时没有加载成功，请重试。", 502) from exc

    return routes
