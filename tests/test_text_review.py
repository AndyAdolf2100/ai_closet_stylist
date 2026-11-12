import json

import httpx
import pytest
from fastapi.testclient import TestClient

from stylist.config import Settings
from stylist.engine import Stylist
from stylist.errors import AuthenticationExpired, StylistError
from stylist.main import create_app
from stylist.memory import MemoryBook, MemoryEntry, apply_memory
from stylist.models import Change, Plan, Task
from stylist.store import Store
from stylist.text_review import REJECTED_MESSAGE, UNAVAILABLE_MESSAGE
from stylist.upstream import Upstream


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data,code",
    [
        ({"passed": True, "risk_level": "PASS"}, None),
        ({"passed": False, "risk_level": "REVIEW"}, "text_check_rejected"),
        ({"passed": False, "risk_level": "REJECT"}, "text_check_rejected"),
        ({"passed": True, "risk_level": "REJECT"}, "text_check_unavailable"),
        ({"passed": False, "risk_level": "PASS"}, "text_check_unavailable"),
        ({"passed": "true", "risk_level": "PASS"}, "text_check_unavailable"),
        ({"passed": True}, "text_check_unavailable"),
        ({"passed": False, "risk_level": []}, "text_check_unavailable"),
        ({}, "text_check_unavailable"),
        (None, "text_check_unavailable"),
        ("PASS", "text_check_unavailable"),
    ],
)
async def test_text_review_fixed_authenticated_contract_and_strict_verdict(data, code):
    def handler(request):
        assert request.method == "POST"
        assert str(request.url) == "https://server.invalid/api/risk/text_check"
        assert request.headers["Authorization"] == "Bearer synthetic-user"
        assert json.loads(request.content) == {"text": "我喜欢清爽"}
        return httpx.Response(200, json={"code": 0, "data": data})

    upstream = Upstream(
        Settings(server_url="https://server.invalid"),
        "Bearer synthetic-user",
        transport=httpx.MockTransport(handler),
    )
    if code:
        with pytest.raises(StylistError) as error:
            await upstream.check_text("  我喜欢清爽  ")
        assert error.value.code == code
    else:
        assert await upstream.check_text("  我喜欢清爽  ") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["44100", "404", "500", "timeout", "bad-json", "list", "missing-code"])
async def test_text_review_failure_is_closed_and_uses_safe_friendly_message(mode):
    def handler(request):
        if mode == "timeout":
            raise httpx.ReadTimeout("synthetic-secret", request=request)
        if mode == "bad-json":
            return httpx.Response(200, text="synthetic-secret")
        if mode == "list":
            return httpx.Response(200, json=[])
        if mode == "missing-code":
            return httpx.Response(200, json={"data": {"passed": True, "risk_level": "PASS"}})
        if mode == "44100":
            return httpx.Response(200, json={"code": 44100, "msg": "synthetic-secret"})
        return httpx.Response(int(mode), text="synthetic-secret")

    upstream = Upstream(Settings(), "Bearer synthetic", transport=httpx.MockTransport(handler))
    with pytest.raises(StylistError) as error:
        await upstream.check_text("我喜欢宽松衣服")
    assert error.value.code == "text_check_unavailable"
    assert error.value.message == UNAVAILABLE_MESSAGE
    assert "synthetic-secret" not in error.value.message


@pytest.mark.asyncio
@pytest.mark.parametrize("status,payload", [(401, {}), (403, {}), (200, {"code": 43101})])
async def test_text_review_preserves_authentication_expiry(status, payload):
    upstream = Upstream(
        Settings(),
        "Bearer synthetic",
        transport=httpx.MockTransport(lambda _: httpx.Response(status, json=payload)),
    )
    with pytest.raises(AuthenticationExpired):
        await upstream.check_text("衣服")


@pytest.mark.asyncio
async def test_unicode_character_limit_without_network_for_invalid_input():
    calls = []

    def handler(request):
        calls.append(json.loads(request.content)["text"])
        return httpx.Response(200, json={"code": 0, "data": {"passed": True, "risk_level": "PASS"}})

    upstream = Upstream(Settings(), "Bearer synthetic", transport=httpx.MockTransport(handler))
    await upstream.check_text("😀" * 10000)
    for text in ["", "  ", "😀" * 10001]:
        with pytest.raises(StylistError, match="text_check_invalid"):
            await upstream.check_text(text)
    assert len(calls) == 1


@pytest.fixture
def api(tmp_path, monkeypatch):
    settings = Settings(database=str(tmp_path / "manual.db"), server_url="https://server.invalid")
    calls, verdict = [], {"data": {"passed": True, "risk_level": "PASS", "filtered_text": "不得替换用户原稿"}}
    original = Upstream.__init__

    def handler(request):
        assert str(request.url) == "https://server.invalid/api/risk/text_check"
        calls.append((request.headers["Authorization"], json.loads(request.content)))
        return httpx.Response(200, json={"code": verdict.get("code", 0), "data": verdict["data"]})

    def init(self, settings, authorization, transport=None):
        original(self, settings, authorization, transport=httpx.MockTransport(handler))

    async def identity(self):
        return self.authorization.removeprefix("Bearer ")

    monkeypatch.setattr(Upstream, "__init__", init)
    monkeypatch.setattr(Upstream, "identity", identity)
    with TestClient(create_app(settings)) as client:
        yield client, settings, calls, verdict


def body(text="舒服自在就很好", revision=0):
    return {"revision": revision, "enabled": True, "entries": [{"id": "note", "content": text}]}


def test_manual_api_reviews_then_persists_original_without_keyword_gate(api):
    client, settings, calls, _ = api
    headers = {"Authorization": "Bearer owner-a"}
    response = client.put("/stylist-api/memories", headers=headers, json=body())
    assert response.status_code == 200
    assert response.json()["entries"][0]["content"] == "舒服自在就很好"
    assert calls == [("Bearer owner-a", {"text": "舒服自在就很好"})]
    assert client.get("/stylist-api/memories", headers=headers).json() == response.json()
    assert Store(settings.database).memory_book("owner-a").entries[0].content == "舒服自在就很好"
    assert (
        client.get("/stylist-api/memories", headers={"Authorization": "Bearer owner-b"}).json()["entries"]
        == []
    )
    assert "_manual_entries" not in json.dumps(response.json())


@pytest.mark.parametrize("risk", ["REVIEW", "REJECT"])
def test_rejected_api_does_not_write_or_advance_revision(api, risk):
    client, settings, _, verdict = api
    headers = {"Authorization": "Bearer owner-a"}
    saved = client.put("/stylist-api/memories", headers=headers, json=body()).json()
    verdict["data"] = {"passed": False, "risk_level": risk, "risk_description": "synthetic-secret"}
    response = client.put("/stylist-api/memories", headers=headers, json=body("另一段想留下的内容", 1))
    assert response.status_code == 422
    assert response.json() == {"code": "text_check_rejected", "message": REJECTED_MESSAGE}
    assert client.get("/stylist-api/memories", headers=headers).json() == saved
    assert Store(settings.database).memory_book("owner-a").revision == 1


def test_failure_auth_invalid_conflict_empty_and_retry(api):
    client, settings, calls, verdict = api
    headers = {"Authorization": "Bearer owner-a"}
    assert client.put("/stylist-api/memories", json=body()).status_code == 401
    invalid = body()
    invalid["entries"][0]["content"] = " "
    assert client.put("/stylist-api/memories", headers=headers, json=invalid).status_code == 422
    assert not calls
    verdict["code"] = 44100
    response = client.put("/stylist-api/memories", headers=headers, json=body())
    assert response.status_code == 503 and response.json()["message"] == UNAVAILABLE_MESSAGE
    assert Store(settings.database).memory_book("owner-a").revision == 0
    verdict["code"] = 0
    assert client.put("/stylist-api/memories", headers=headers, json=body()).status_code == 200
    count = len(calls)
    assert client.put("/stylist-api/memories", headers=headers, json=body()).status_code == 409
    assert len(calls) == count
    response = client.put(
        "/stylist-api/memories", headers=headers, json={"revision": 1, "enabled": False, "entries": []}
    )
    assert response.status_code == 200 and response.json()["entries"] == []
    assert len(calls) == count


def test_batch_one_call_including_paused_book_and_max_unicode_pages(api):
    client, _, calls, _ = api
    payload = {
        "revision": 0,
        "enabled": False,
        "entries": [{"id": f"n{i}", "content": str(i) + "😀" * 238} for i in range(30)],
    }
    response = client.put("/stylist-api/memories", headers={"Authorization": "Bearer owner-a"}, json=payload)
    assert response.status_code == 200
    assert len(calls) == 1
    assert calls[0][1] == {"text": "\n".join(e["content"] for e in payload["entries"])}
    assert len(calls[0][1]["text"]) < 10000


@pytest.mark.asyncio
async def test_manual_notes_reach_context_without_old_keyword_filter_and_pause_still_applies(tmp_path):
    store = Store(str(tmp_path / "context.db"))
    saved = store.save_memory_book(
        "a", MemoryBook(entries=[MemoryEntry(id="manual", content="舒服自在就很好")]), manual=True
    )
    engine = Stylist(Settings(), store, None)
    snapshot = await engine.memory_snapshot("a")
    assert snapshot[0]["content"] == "舒服自在就很好"
    task = apply_memory(
        Task(),
        Plan(
            mode="consult", memory_changes={"preferences": Change(value=["舒适"], evidence="舒服自在就很好")}
        ),
        snapshot,
    )
    assert task.preferences == ["舒适"]
    assert apply_memory(Task(target_description="朋友"), Plan(mode="consult"), snapshot).preferences == []
    saved.enabled = False
    store.save_memory_book("a", saved, manual=True)
    assert await engine.memory_snapshot("a") == []


def test_only_deleting_or_toggling_does_not_require_service_and_keeps_original_notes(api):
    client, settings, calls, verdict = api
    headers = {"Authorization": "Bearer owner-a"}
    payload = body()
    payload["entries"].append({"id": "second", "content": "简简单单就很好"})
    assert client.put("/stylist-api/memories", headers=headers, json=payload).status_code == 200
    count = len(calls)
    verdict["code"] = 44100
    payload.update(revision=1, enabled=False)
    payload["entries"] = payload["entries"][:1]
    paused = client.put("/stylist-api/memories", headers=headers, json=payload)
    assert paused.status_code == 200 and paused.json()["enabled"] is False
    assert len(calls) == count
    assert Store(settings.database).memory_book("owner-a").entries[0].content == "舒服自在就很好"
    payload.update(revision=2, enabled=True)
    assert client.put("/stylist-api/memories", headers=headers, json=payload).status_code == 200
    assert len(calls) == count
    payload.update(revision=3, entries=[])
    assert client.put("/stylist-api/memories", headers=headers, json=payload).status_code == 200
    assert len(calls) == count


def test_client_cannot_bypass_review_with_unknown_flags(api):
    client, _, calls, _ = api
    payload = body()
    payload["review_passed"] = True
    response = client.put("/stylist-api/memories", headers={"Authorization": "Bearer owner-a"}, json=payload)
    assert response.status_code == 422 and not calls


def test_revision_is_rechecked_after_audit_to_prevent_overwriting_concurrent_save(api, monkeypatch):
    client, settings, calls, _ = api

    async def concurrent_review(self, text):
        Store(settings.database).save_memory_book(
            "owner-a", MemoryBook(entries=[MemoryEntry(id="other", content="另一处修改的原稿")]), manual=True
        )

    monkeypatch.setattr(Upstream, "check_text", concurrent_review)
    response = client.put("/stylist-api/memories", headers={"Authorization": "Bearer owner-a"}, json=body())
    assert response.status_code == 409 and not calls
    saved = Store(settings.database).memory_book("owner-a")
    assert saved.revision == 1 and saved.entries[0].content == "另一处修改的原稿"


@pytest.mark.asyncio
async def test_manual_notes_survive_chat_addition_and_reach_plan_and_style(tmp_path):
    from stylist.models import ChatRequest, Draft

    store = Store(str(tmp_path / "chat.db"))
    store.save_memory_book(
        "a", MemoryBook(entries=[MemoryEntry(id="manual", content="舒服自在就很好")]), manual=True
    )

    class User:
        async def identity(self):
            return "a"

    class Model:
        def __init__(self):
            self.calls = []

        async def generate(self, name, payload, result_type):
            self.calls.append((name, payload))
            if name == "plan":
                return Plan(mode="consult", use_inventory=False, conversation_only=True)
            return Draft(message="可以先从舒服自在的穿着聊起。")

    model = Model()
    engine = Stylist(Settings(), store, model)
    await engine.chat(User(), ChatRequest(message="只说文字，聊聊日常穿搭。", request_id="manual-context"))
    for name, payload in model.calls:
        if name in {"plan", "style"}:
            assert any(note["content"] == "舒服自在就很好" for note in payload["long_term_memory"])
    await engine.chat(User(), ChatRequest(message="记住：我不穿高跟鞋", request_id="chat-add"))
    reopened = Store(store.path).memory_book("a")
    assert any(note.content == "舒服自在就很好" for note in reopened.entries)
    assert any(note.content == "我不穿高跟鞋" for note in reopened.entries)
