"""Fixed read boundaries for the existing Go service; no arbitrary model-selected URL/tool."""
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import timedelta

import httpx
from jsonschema import Draft202012Validator
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from .config import Settings
from .errors import AuthenticationExpired, StylistError

READ_TOOLS = {"city.resolve", "weather.get", "product.resolve", "outfit.search-saved", "outfit.resolve", "kb_search"}
IMAGE_READ_TOOLS = {"digital_twin_overview", "digital_twin_tryon_quote", "product_beautify_quote"}
READ_TOOLS |= IMAGE_READ_TOOLS
AUTH_CODES = {401, 403, 43100, 43101, 43102, 43103}


def _is_auth(exc):
    return isinstance(exc, AuthenticationExpired) or (
        isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {401, 403}
    ) or any(_is_auth(x) for x in getattr(exc, "exceptions", ()))


def _business_payload(response: httpx.Response):
    if response.status_code in {401, 403}:
        raise AuthenticationExpired()
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict) or "code" not in value:
        raise StylistError("upstream_contract_error", "服务返回格式异常，请稍后重试。")
    if value.get("msg") == "版本错误！":
        raise StylistError("upstream_headers_invalid", "服务请求缺少有效版本信息。")
    if value["code"] in AUTH_CODES:
        raise AuthenticationExpired()
    if value["code"] != 0:
        raise StylistError("upstream_business_error", "当前服务暂不可用，请稍后重试。")
    return value.get("data")


class Upstream:
    def __init__(self, settings: Settings, authorization: str, transport=None):
        self.settings = settings
        self.authorization = authorization
        self.transport = transport

    async def get(self, path: str, params=None):
        allowed = {"/api/user/info", "/api/user_product/quick_edit_list", "/api/product/list", "/api/memories"}
        if path not in allowed:
            raise StylistError("endpoint_not_allowed", "该接口未接入。", 400)
        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout, trust_env=False,
                                         transport=self.transport) as client:
                response = await client.get(self.settings.server_url + path, params=params,
                                            headers={"Authorization": self.authorization,
                                                     "version": self.settings.login_app_version, "device": "PC"})
                return _business_payload(response)
        except (httpx.HTTPError, ValueError) as exc:
            raise StylistError("upstream_unavailable", "当前服务连接失败，请稍后重试。") from exc

    async def identity(self) -> str:
        info = await self.get("/api/user/info")
        owner = str(info.get("id", "")) if isinstance(info, dict) else ""
        if not owner.isdecimal() or int(owner) < 1:
            raise StylistError("identity_contract_error", "无法确认当前账号，请重新登录。", 401)
        return owner

    async def forecast(self, city):
        """Existing read-only day/night forecast, despite the upstream POST verb."""
        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout, trust_env=False,
                                         transport=self.transport) as client:
                response = await client.post(self.settings.server_url + "/api/weather/get_weather",
                    json={"city_name": city["city_name"], "province_name": city["province_name"], "days": 14},
                    headers={"Authorization": self.authorization,
                             "version": self.settings.login_app_version, "device": "PC"})
                return _business_payload(response)
        except (httpx.HTTPError, ValueError) as exc:
            raise StylistError("forecast_unavailable", "多日预报暂时没有取到，可以稍后重试。") from exc

    @asynccontextmanager
    async def mcp(self, image=False):
        async def check(response):
            if response.status_code in {401, 403}:
                raise AuthenticationExpired()
        try:
            async with (
                httpx.AsyncClient(headers={"Authorization": self.authorization}, trust_env=False,
                                  timeout=self.settings.image_timeout if image else self.settings.request_timeout,
                                  event_hooks={"response": [check]},
                                  transport=self.transport) as client,
                streamable_http_client(self.settings.mcp_url, http_client=client,
                                       terminate_on_close=False) as (read, write, _),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                yield MCPReads(session, self.settings.request_timeout, self.settings.image_timeout)
        except Exception as exc:
            if _is_auth(exc):
                raise AuthenticationExpired() from None
            # ExceptionGroups from the transport must not erase our business error.
            pending = [exc]
            while pending:
                item = pending.pop()
                if isinstance(item, StylistError):
                    raise item from None
                pending.extend(getattr(item, "exceptions", ()))
            raise StylistError("mcp_unavailable", "衣橱工具服务暂不可用，请稍后重试。") from exc


class MCPReads:
    def __init__(self, session, timeout=20, image_timeout=240):
        self.session, self.timeout, self.tools = session, timeout, None
        self.image_timeout = image_timeout

    async def discover(self):
        if self.tools is None:
            self.tools = {}
            cursor = None
            for _ in range(10):
                result = await self.session.list_tools(cursor=cursor)
                self.tools.update({t.name: t for t in result.tools})
                cursor = result.nextCursor
                if not cursor:
                    return self.tools
            raise StylistError("tool_catalog_truncated", "工具目录读取不完整。")
        return self.tools

    async def call(self, name, arguments):
        if name not in READ_TOOLS:
            raise StylistError("tool_not_allowed", "该操作未接入，不会执行。", 400)
        return await self._validated_call(name, arguments)

    async def commit_image(self, name, arguments):
        # Only ImageService may use this after a durable explicit confirmation.
        if name not in {"save_recommended_outfit", "digital_twin_tryon"}:
            raise StylistError("tool_not_allowed", "该图像操作未接入。", 400)
        return await self._validated_call(name, arguments, timeout=self.image_timeout)

    async def _validated_call(self, name, arguments, timeout=None):
        tool = (await self.discover()).get(name)
        if tool is None:
            raise StylistError("tool_missing", "当前服务尚未提供所需能力。")
        if list(Draft202012Validator(tool.inputSchema).iter_errors(arguments)):
            raise StylistError("tool_input_invalid", "工具参数校验失败。", 400)
        result = await self.session.call_tool(name, arguments,
                                              read_timeout_seconds=timedelta(seconds=timeout or self.timeout))
        value = result.structuredContent
        if value is None:
            for content in result.content:
                if getattr(content, "type", "") == "text":
                    try:
                        value = json.loads(content.text)
                    except ValueError:
                        pass
        if result.isError:
            code = value.get("code", "tool_error") if isinstance(value, dict) else "tool_error"
            if code in {"unauthenticated", "unauthorized", "authentication_expired"}:
                raise AuthenticationExpired()
            raise StylistError(code, "该服务暂时无法完成请求。")
        if not isinstance(value, dict):
            raise StylistError("tool_result_invalid", "工具返回结果不完整。")
        if tool.outputSchema and list(Draft202012Validator(tool.outputSchema).iter_errors(value)):
            raise StylistError("tool_result_invalid", "工具返回结果不符合接口约定。")
        return value


async def check_integrations(upstream: Upstream):
    """Perform actual authenticated reads. Persist only this metadata, never returned user data."""
    from time import perf_counter

    results = []

    async def probe(name, call):
        start = perf_counter()
        try:
            data = await call()
            record = {"interface": name, "status": "ok", "code": "ok",
                      "latency_ms": round((perf_counter() - start) * 1000)}
            if name == "weather.get" and isinstance(data, dict):
                record["facts"] = {k: data[k] for k in ["city_name", "date", "temp", "condition"]}
            if name in {"digital_twin_tryon_quote", "product_beautify_quote"} and isinstance(data, dict):
                record["points_cost"] = data.get("points_cost")
            results.append(record)
            return data
        except StylistError as exc:
            results.append({"interface": name, "status": "failed", "code": exc.code,
                            "latency_ms": round((perf_counter() - start) * 1000)})
        return None

    identity = await probe("GET /api/user/info", upstream.identity)
    if identity is None:
        for name in ["GET /api/user_product/quick_edit_list", "GET /api/memories",
                     "MCP tools/list", *sorted(READ_TOOLS)]:
            results.append({"interface": name, "status": "blocked", "code": "identity_failed"})
        return results
    wardrobe, _ = await asyncio.gather(
        probe("GET /api/user_product/quick_edit_list",
              lambda: upstream.get("/api/user_product/quick_edit_list", {"page": 1, "page_size": 20, "is_ai_outfit": 1})),
        probe("GET /api/memories", lambda: upstream.get("/api/memories")),
    )
    try:
        async with upstream.mcp() as mcp:
            tools = await probe("MCP tools/list", mcp.discover)
            for name in ["digital_twin_tryon", "digital_twin_generate", "product_beautify", "save_recommended_outfit"]:
                results.append({"interface": name, "status": "published_not_executed" if tools and name in tools else "not_published",
                                "code": "write_operation_not_probed"})
            cities = await probe("city.resolve", lambda: mcp.call("city.resolve", {"name": "北京"}))
            if cities and cities.get("status") == "resolved" and len(cities.get("matches", [])) == 1:
                city = cities["matches"][0]
                await probe("weather.get", lambda: mcp.call("weather.get", {
                    "city_name": city["city_name"], "province_name": city["province_name"]}))
            else:
                results.append({"interface": "weather.get", "status": "blocked", "code": "city_unresolved"})
            refs = []
            if wardrobe and wardrobe.get("list"):
                refs.append({"source": "user", "product_id": str(wardrobe["list"][0]["user_product_id"])})
            if refs:
                await probe("product.resolve", lambda: mcp.call("product.resolve", {"items": refs}))
            else:
                results.append({"interface": "product.resolve", "status": "blocked", "code": "no_product_fixture"})
            outfits = await probe("outfit.search-saved", lambda: mcp.call("outfit.search-saved", {"occasion": "日常"}))
            if outfits and outfits.get("matches"):
                outfit_id = outfits["matches"][0]["outfit_id"]
                await probe("outfit.resolve", lambda: mcp.call("outfit.resolve", {
                    "source": "user", "outfit_id": outfit_id, "include_presentation": True}))
            else:
                results.append({"interface": "outfit.resolve", "status": "blocked", "code": "no_outfit_fixture"})
            for scope in ["user"]:
                await probe(f"kb_search:{scope}", lambda scope=scope: mcp.call("kb_search", {
                    "query": "日常通勤上衣", "gender": "女", "scope": scope, "top_k": 3}))
            await probe("digital_twin_overview", lambda: mcp.call("digital_twin_overview", {}))
            await probe("digital_twin_tryon_quote", lambda: mcp.call("digital_twin_tryon_quote", {}))
            user_rows = (wardrobe or {}).get("list") or []
            uploaded = next((row for row in user_rows if not row.get("product_id", 0)), None)
            if uploaded:
                await probe("product_beautify_quote", lambda: mcp.call("product_beautify_quote", {
                    "user_product_id": int(uploaded["user_product_id"])}))
            else:
                results.append({"interface": "product_beautify_quote", "status": "blocked", "code": "no_uploaded_product_fixture"})
    except StylistError as exc:
        seen = {x["interface"] for x in results}
        for name in ["MCP tools/list", *sorted(READ_TOOLS)]:
            if name not in seen:
                results.append({"interface": name, "status": "failed", "code": exc.code})
    return results
