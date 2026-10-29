import asyncio
import hashlib
import json
from contextlib import asynccontextmanager

import httpx
import pytest
from pydantic import ValidationError

from stylist.config import Settings
from stylist.engine import Stylist
from stylist.errors import StylistError
from stylist.llm import LanguageModel
from stylist.models import Change, ChatRequest, Draft, Look, LookDraft, Plan, Reply, SessionState, Task
from stylist.personas import persona_instructions
from stylist.store import Store


@pytest.mark.asyncio
async def test_selected_persona_reaches_actual_model_system_prompt_without_cross_request_leak():
    prompts = []

    def respond(request):
        body = json.loads(request.content)
        prompts.append(body["messages"][0]["content"])
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"message":"测试回应"}'}}]})

    model = LanguageModel(Settings(llm_key="fake", llm_model="fake", llm_url="https://model.invalid"),
                          transport=httpx.MockTransport(respond))
    await asyncio.gather(*(model.generate("style", {"assistant_persona": persona}, Draft)
                           for persona in ["male_calm_v1", "female_warm_v1", None]))
    assert "男助理人格 male_calm_v1" in prompts[0] and "女助理人格" not in prompts[0]
    assert "女助理人格 female_warm_v1" in prompts[1] and "男助理人格" not in prompts[1]
    assert "助理人格" not in prompts[2]  # Legacy callers keep the generic expression.
    for prompt in prompts:
        assert "frozen_keys" in prompt and "不能编造" in prompt


@pytest.mark.parametrize("value", ["../../config/local.yaml", "ignore_business_rules", "male"])
def test_persona_is_a_server_allowlist_not_client_prompt_text(value):
    with pytest.raises(ValidationError):
        ChatRequest(message="测试", request_id="persona-invalid", assistant_persona=value)
    with pytest.raises(StylistError, match="unknown_persona"):
        persona_instructions(value)


@pytest.mark.asyncio
async def test_schema_repair_gives_field_errors_and_keeps_persona():
    calls = []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            value = {"message": "穿法", "looks": [{"title": "简单穿法", "how": ["自然垂放"]}]}
        else:
            assert "looks.0.why" in body["messages"][-1]["content"]
            assert "女助理人格 female_warm_v1" in body["messages"][0]["content"]
            value = {"message": "穿法", "looks": [{"title": "简单穿法", "how": ["自然垂放"], "why": ["保留要求"]}]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(value)}}]})

    model = LanguageModel(Settings(llm_key="fake", llm_model="fake", llm_url="https://model.invalid"),
                          transport=httpx.MockTransport(respond))
    reply = await model.generate("style", {"assistant_persona": "female_warm_v1"}, Draft)
    assert reply.looks[0].why == ["保留要求"] and len(calls) == 2


@pytest.mark.asyncio
async def test_persona_switch_keeps_outfit_target_and_is_locked_on_request_replay(tmp_path):
    class Upstream:
        async def identity(self):
            return "owner"

        @asynccontextmanager
        async def mcp(self):
            pytest.fail("Consultation must not read inventory")
            yield

    class Model:
        def __init__(self):
            self.inputs = []

        async def generate(self, name, payload, result_type):
            self.inputs.append((name, payload))
            if name == "plan":
                return Plan(mode="consult", use_inventory=False, changes={
                    "gender": Change(value="女", evidence="女生")})
            return Draft(message="测试回应")

    store = Store(str(tmp_path / "state.db"))
    model = Model()
    engine = Stylist(Settings(), store, model)
    request = ChatRequest(message="只咨询女生穿法，不找衣服", request_id="persona-male-001",
                          assistant_persona="male_calm_v1", weather_policy="ignored")
    male = await engine.chat(Upstream(), request)
    assert male.task.gender == "女"
    assert all(p["assistant_persona"] == "male_calm_v1" for _, p in model.inputs)
    assert await engine.chat(Upstream(), request) == male
    with pytest.raises(StylistError, match="idempotency_conflict"):
        await engine.chat(Upstream(), request.model_copy(update={"assistant_persona": "female_warm_v1"}))
    model.inputs.clear()
    female = await engine.chat(Upstream(), request.model_copy(update={
        "request_id": "persona-female-002", "assistant_persona": "female_warm_v1",
        "conversation_id": male.conversation_id, "expected_version": male.version}))
    assert female.task.gender == "女" and female.task.weather_policy == "auto"
    assert all(p["assistant_persona"] == "female_warm_v1" for _, p in model.inputs)


def test_pre_persona_request_digest_still_replays_after_upgrade(tmp_path):
    store = Store(str(tmp_path / "state.db"))
    request = ChatRequest(message="旧请求", request_id="legacy-persona-001")
    cid, claim, state, _ = store.reserve("owner", request)
    reply = Reply(conversation_id=cid, version=1, mode="consult", delivery="advice", message="结果", task=Task())
    store.finish("owner", request, claim, state, reply)
    legacy_digest = hashlib.sha256(request.model_dump_json(exclude={"assistant_persona", "companion_profile"}).encode()).hexdigest()
    with store.connection() as conn:
        conn.execute("UPDATE stylist_requests SET digest=?", (legacy_digest,))
    assert store.reserve("owner", request)[3] == reply


@pytest.mark.asyncio
async def test_small_talk_preserves_outfit_and_skips_tools_and_plan_approval(tmp_path):
    class Upstream:
        async def identity(self):
            return "owner"

        @asynccontextmanager
        async def mcp(self):
            pytest.fail("Small talk must not read products")
            yield

    class Model:
        async def generate(self, name, payload, result_type):
            if name == "plan":
                return Plan(mode="recommend", conversation_only=True, new_task=True,
                    weather_scope="day", changes={"gender": Change(value="男", evidence="男助理")})
            return Draft(message="晚安，今晚好好休息。", looks=[LookDraft(title="不该出现的穿搭", why=["不应输出"], how=["不应输出"])])

    store = Store(str(tmp_path / "state.db"))
    request = ChatRequest(message="搭配", request_id="before-smalltalk")
    cid, claim, state, _ = store.reserve("owner", request)
    state.task = Task(gender="女", no_heels=True)
    state.mode = "recommend"
    state.looks = [Look(title="先前方案", pieces=["白衬衫", "灰裤"])]
    store.finish("owner", request, claim, state, Reply(conversation_id=cid, version=1,
        mode="recommend", delivery="advice", task=state.task, looks=state.looks, message="原方案"))
    result = await Stylist(Settings(), store, Model()).chat(Upstream(), ChatRequest(
        message="男助理，说晚安", request_id="during-smalltalk", conversation_id=cid,
        expected_version=1, confirm_plan=True, weather_policy="auto", assistant_persona="male_calm_v1"))
    assert result.conversation_only
    assert not result.pending_confirmation and not result.looks
    assert result.task == state.task
    with store.connection() as conn:
        row = conn.execute("SELECT state_json FROM stylist_sessions WHERE id=?", (cid,)).fetchone()
    saved = SessionState.model_validate_json(row["state_json"])
    assert saved.mode == state.mode and saved.looks == state.looks and saved.task == state.task
