"""Fixed Server text compliance boundary; never log content or risk credentials."""
import httpx

from .errors import AuthenticationExpired, StylistError

REJECTED_MESSAGE = "这段文字暂时还不能收进手记。换个说法再试试吧，刚才写的内容还在。"
UNAVAILABLE_MESSAGE = "这几页还没收好，文字检查暂时没能完成。内容还在，稍后再试一次就好。"


async def review_text(upstream, text):
    from .upstream import _business_payload

    text = text.strip()
    if not text or len(text) > 10000:
        raise StylistError("text_check_invalid", "这段文字还没整理好，调整一下再试试吧。", 422)
    try:
        async with httpx.AsyncClient(timeout=upstream.settings.request_timeout, trust_env=False,
                                     transport=upstream.transport) as client:
            response = await client.post(upstream.settings.server_url + "/api/risk/text_check",
                headers={"Authorization": upstream.authorization,
                         "version": upstream.settings.login_app_version, "device": "PC"},
                json={"text": text})
        data = _business_payload(response)
    except AuthenticationExpired:
        raise
    except (httpx.HTTPError, ValueError, TypeError, StylistError) as exc:
        raise StylistError("text_check_unavailable", UNAVAILABLE_MESSAGE) from exc
    if not isinstance(data, dict):
        raise StylistError("text_check_unavailable", UNAVAILABLE_MESSAGE)
    level = data.get("risk_level")
    if not isinstance(level, str):
        raise StylistError("text_check_unavailable", UNAVAILABLE_MESSAGE)
    if data.get("passed") is True and level == "PASS":
        return
    if data.get("passed") is False and level in {"REVIEW", "REJECT"}:
        raise StylistError("text_check_rejected", REJECTED_MESSAGE, 422)
    # Missing, unknown or inconsistent verdicts must never become success.
    raise StylistError("text_check_unavailable", UNAVAILABLE_MESSAGE)
