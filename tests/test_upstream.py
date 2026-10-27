from types import SimpleNamespace

import httpx
import pytest

from stylist.config import Settings
from stylist.errors import AuthenticationExpired, StylistError
from stylist.upstream import MCPReads, Upstream


@pytest.mark.asyncio
@pytest.mark.parametrize("status,body", [(401, {}),
    (200, {"code": 43100, "msg": "帐号已在其他地方登录", "data": None}),
    (200, {"code": 43101, "msg": "授权token错误", "data": None}),
    (200, {"code": 43102, "msg": "登陆已过期，请重新登陆", "data": None}),
    (200, {"code": 43103, "msg": "您的帐号已在其他地方登录，如非本人操作，请注意帐号安全。", "data": None})])
async def test_auth_failure_is_not_city_failure(status, body):
    upstream = Upstream(Settings(), "Bearer test", httpx.MockTransport(lambda r: httpx.Response(status, json=body)))
    with pytest.raises(AuthenticationExpired):
        await upstream.identity()


@pytest.mark.asyncio
async def test_rest_sends_required_version_and_does_not_trust_client_user_id():
    def handler(request):
        assert request.headers["version"] == "1.2.0"
        assert request.headers["authorization"] == "Bearer test"
        assert "X-User-ID" not in request.headers
        return httpx.Response(200, json={"code": 0, "data": {"id": 7, "mobile": "not_returned"}})
    assert await Upstream(Settings(), "Bearer test", httpx.MockTransport(handler)).identity() == "7"


@pytest.mark.asyncio
async def test_version_configuration_error_is_not_reported_as_login_expiry():
    upstream = Upstream(Settings(), "Bearer test", httpx.MockTransport(
        lambda r: httpx.Response(200, json={"code": 43100, "msg": "版本错误！"})))
    with pytest.raises(StylistError, match="upstream_headers_invalid"):
        await upstream.identity()


@pytest.mark.asyncio
async def test_tool_input_and_output_contracts_are_checked():
    tool = SimpleNamespace(name="weather.get", inputSchema={"type": "object", "required": ["city_name"]},
                           outputSchema={"type": "object", "required": ["temp"]})
    class Session:
        async def list_tools(self, cursor=None):
            return SimpleNamespace(tools=[tool], nextCursor=None)
        async def call_tool(self, *args, **kwargs):
            return SimpleNamespace(structuredContent={"condition": "晴"}, content=[], isError=False)
    reads = MCPReads(Session())
    with pytest.raises(StylistError, match="tool_input_invalid"):
        await reads.call("weather.get", {})
    with pytest.raises(StylistError, match="tool_result_invalid"):
        await reads.call("weather.get", {"city_name": "北京"})
    with pytest.raises(StylistError, match="tool_not_allowed"):
        await reads.call("digital_twin_tryon", {})
