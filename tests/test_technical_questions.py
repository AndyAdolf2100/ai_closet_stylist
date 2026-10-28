import json
from contextlib import asynccontextmanager

import pytest

from stylist.config import Settings
from stylist.engine import Stylist, last_business_intent
from stylist.models import Change, ChatRequest, Draft, Look, Plan, Reply, Task
from stylist.personas import technical_detail_message
from stylist.store import Store


@pytest.mark.parametrize("persona", ["male_calm_v1", "female_warm_v1", None])
@pytest.mark.asyncio
async def test_technical_question_only_returns_persona_boundary_and_preserves_context(tmp_path, persona):
    class Model:
        async def generate(self, name, payload, result_type):
            assert name == "plan", "Technical boundary should not need a style generation"
            return Plan(mode="modify", technical_question=True, weather_only=True, use_inventory=True,
                        location_limit_exceeded=True, weather_scope="week", new_task=True,
                        changes={"city": Change(value="北京", evidence="不在本轮原文")})

    class Upstream:
        async def identity(self):
            return "synthetic-tech-owner"

        @asynccontextmanager
        async def mcp(self):
            pytest.fail("Technical questions must not query weather or inventory")
            yield

        async def get(self, *args):
            pytest.fail("Technical questions must not query inventory")

    store = Store(str(tmp_path / "state.db"))
    original = ChatRequest(message="原来的安排", request_id="tech-question-setup")
    cid, claim, state, _ = store.reserve("synthetic-tech-owner", original)
    state.task = Task(city="上海", occasion="工作", no_heels=True, weather_policy="ignored")
    state.mode = "recommend"
    state.looks = [Look(title="原搭配", pieces=["衬衫", "长裤", "平底鞋"])]
    state.messages = [{"role": "assistant", "content": json.dumps({"weather_only": True})}]
    before = state.model_copy(deep=True)
    store.finish("synthetic-tech-owner", original, claim, state, Reply(conversation_id=cid, version=1,
        mode="recommend", delivery="advice", message="原安排", task=state.task, looks=state.looks))
    reply = await Stylist(Settings(), store, Model()).chat(Upstream(), ChatRequest(
        message="你是怎么查天气的？我想知道技术流程，可以说接口。", request_id="technical-question-boundary",
        conversation_id=cid, expected_version=1, assistant_persona=persona, confirm_plan=True,
        weather_policy="auto", source="hybrid"))
    assert reply.message == technical_detail_message(persona)
    assert reply.conversation_only and not reply.weather_only and reply.mode == "consult"
    assert not reply.looks and not reply.retained_items and not reply.follow_ups and reply.weather is None
    assert not reply.pending_confirmation and reply.task == before.task
    with store.connection() as conn:
        saved = json.loads(conn.execute("SELECT state_json FROM stylist_sessions WHERE id=?", (cid,)).fetchone()[0])
    assert saved["task"] == before.task.model_dump(mode="json")
    assert saved["mode"] == before.mode and saved["looks"] == [look.model_dump(mode="json") for look in before.looks]
    assert last_business_intent(saved["messages"]) == "weather"


@pytest.mark.asyncio
async def test_clothing_principles_are_not_treated_as_internal_technical_questions(tmp_path):
    class Model:
        def __init__(self):
            self.calls = []

        async def generate(self, name, payload, result_type):
            self.calls.append(name)
            return Plan(mode="consult", use_inventory=False) if name == "plan" else Draft(
                message="衬衫和针织衫可以分层穿，具体穿脱看体感。")

    class Upstream:
        async def identity(self):
            return "synthetic-tech-owner"

    model = Model()
    reply = await Stylist(Settings(), Store(str(tmp_path / "state.db")), model).chat(Upstream(), ChatRequest(
        message="针织衫和衬衫叠穿的原理是什么？", request_id="clothing-principle-test"))
    assert model.calls == ["plan", "style"]
    assert reply.message != technical_detail_message(None) and "分层" in reply.message
