"""Regression for candidate retention, bounded reads and shared model isolation."""
import asyncio
import json

import httpx
import pytest

from stylist.config import Settings
from stylist.errors import StylistError
from stylist.llm import LanguageModel
from stylist.models import Draft, ProductRef
from stylist.retrieval import resolve_products


@pytest.mark.asyncio
async def test_detail_reads_overlap_with_bound_and_preserve_batch_order():
    class MCP:
        active = 0
        peak = 0

        async def call(self, name, arguments):
            self.active += 1
            self.peak = max(self.peak, self.active)
            await asyncio.sleep(.01)
            self.active -= 1
            return {'items': [dict(ref, class_name='上衣', title=ref['product_id'])
                              for ref in arguments['items']]}

    mcp = MCP()
    refs = [ProductRef(source='user', product_id=str(i)) for i in range(1, 82)]
    result = await resolve_products(mcp, refs + refs[:1])
    assert [p.product_id for p in result] == [str(i) for i in range(1, 82)]
    assert mcp.peak == 3 and mcp.active == 0


@pytest.mark.asyncio
async def test_bad_detail_batch_never_returns_partial_pool_and_drains_siblings():
    class MCP:
        completed = 0

        async def call(self, name, arguments):
            await asyncio.sleep(.01)
            self.completed += 1
            row = arguments['items'][0]
            return {'items': [dict(row, product_id='unexpected', class_name='上衣')]}

    mcp = MCP()
    with pytest.raises(StylistError, match='unexpected_product'):
        await resolve_products(mcp, [ProductRef(source='user', product_id=str(i)) for i in range(1, 42)])
    assert mcp.completed == 3


@pytest.mark.asyncio
async def test_shared_model_keeps_persona_and_attachment_request_local_and_closes():
    bodies = []

    async def handler(request):
        bodies.append(json.loads(request.content))
        await asyncio.sleep(.01)
        return httpx.Response(200, json={'choices': [{'message': {'content': '{"message":"好"}'}}]})

    model = LanguageModel(Settings(llm_key='synthetic', llm_model='synthetic', llm_url='https://model.invalid'),
                          httpx.MockTransport(handler))
    async with model.session():
        client = model._client
        await asyncio.gather(model.generate('style', {'assistant_persona': 'male_calm_v1'}, Draft),
                             model.generate('style', {'assistant_persona': 'female_warm_v1'}, Draft))
        assert model._client is client and not client.is_closed
        assert 'male_calm_v1' in bodies[0]['messages'][0]['content']
        assert 'female_warm_v1' not in bodies[0]['messages'][0]['content']
        assert 'female_warm_v1' in bodies[1]['messages'][0]['content']
        assert 'Authorization' not in client.headers
    assert client.is_closed and model._client is None
    await model.generate('style', {}, Draft)  # One-shot scripts remain usable.


@pytest.mark.asyncio
async def test_saved_style_ranks_before_slot_cutoff_but_explicit_style_wins():
    from stylist.models import Task
    from stylist.retrieval import retrieve

    rows = [dict(source='user', product_id=str(i), user_product_id=str(i),
                 class_name='上衣', style=['优雅' if i == 12 else '休闲']) for i in range(1, 13)]

    class Upstream:
        async def get(self, path, params):
            return {'list': rows, 'pagination': {'total': len(rows)}}

    class MCP:
        async def call(self, name, arguments):
            ids = {r['product_id'] for r in arguments['items']}
            return {'items': [r for r in rows if r['product_id'] in ids]}

    pool, _, _ = await retrieve(Upstream(), MCP(), Task(), '', style_preferences=['优雅'])
    assert next(iter(pool)) == 'user:12' and len(pool) == 10
    pool, _, _ = await retrieve(Upstream(), MCP(), Task(style='休闲'), '', style_preferences=['优雅'])
    assert 'user:12' not in pool and len(pool) == 10


@pytest.mark.asyncio
async def test_payload_compacts_json_and_moves_clock_after_stable_context():
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={'choices': [{'message': {'content': '{"message":"好"}'}}]})

    model = LanguageModel(Settings(llm_key='synthetic', llm_model='synthetic', llm_url='https://model.invalid'),
                          httpx.MockTransport(handler))
    payload = {'now': '2026-11-06T00:00:00+08:00', 'message': '帮我搭一套', 'current_task': {'scene': '通勤'}}
    await model.generate('style', payload, Draft)
    content = bodies[0]['messages'][1]['content']
    assert list(json.loads(content)) == ['message', 'current_task', 'now']
    assert json.loads(content) == payload  # No evidence or user text lost.
    assert payload['now'] == '2026-11-06T00:00:00+08:00'
    assert ': ' not in content


@pytest.mark.asyncio
@pytest.mark.parametrize('count,evidence,expected', [(1, '一套', 1), (2, '一套', None),
                                                   (2, '两套', None), (1, '', None)])
async def test_outfit_count_requires_current_verbatim_number_evidence(count, evidence, expected):
    from stylist.models import Plan, SessionState
    from stylist.policy import interpret_task

    class Model:
        async def generate(self, name, payload, result_type):
            return Plan(mode='recommend', requested_look_count=count, look_count_evidence=evidence)

    plan, _ = await interpret_task(Model(), {}, SessionState(), '本轮套数为一套')
    assert plan.requested_look_count == expected


@pytest.mark.asyncio
async def test_extra_outfit_is_repaired_with_body_rather_than_silently_truncated(tmp_path):
    from scripts.dialogue_validation import DialogueUpstream
    from stylist.engine import Stylist
    from stylist.models import Change, ChatRequest, LookDraft, Plan
    from stylist.store import Store

    class Model:
        style_calls = 0

        async def generate(self, name, payload, result_type):
            if name == 'plan':
                return Plan(mode='recommend', requested_look_count=1, look_count_evidence='一套',
                            changes={'weather_policy': Change(value='ignored', evidence='不考虑天气')})
            self.style_calls += 1
            assert payload['requested_look_count'] == 1
            look = LookDraft(title='日常', selected_keys=['user:101', 'user:102', 'user:103'],
                             why=['白灰配色'], how=['下摆自然放下'])
            if self.style_calls == 1:
                return Draft(message='两套日常方案。', looks=[look, look])
            assert any('最多1套' in error for error in payload['validation_errors'])
            return Draft(message='一套日常方案。', looks=[look])

    model = Model()
    result = await Stylist(Settings(), Store(str(tmp_path / 'count.db')), model).chat(
        DialogueUpstream('wardrobe_only'), ChatRequest(message='给我一套，不考虑天气。', request_id='count-test'))
    assert len(result.looks) == 1 and result.message == '一套日常方案。'
    assert model.style_calls == 2


@pytest.mark.parametrize('message,expected', [
    ('从我的衣橱给我挑一套适合自己的日常搭配', 1), ('帮我搭两套通勤装', 2),
    ('不要一套，要三套', 3), ('不要给我一套搭配，只聊天', None),
    ('比如给我一套通勤装，这只是举例', None), ('他说“给我一套”，我只想聊天', None), ('给我“不要三套”一套', None),
    ('给我2到3套', None), ('给我一到三套', None), ('推荐一套到三套', None),
    ('不查天气，给我1套', 1), ('帮我搭七套，不要一套', 7),
])
def test_explicit_outfit_count_handles_requests_without_routing_negations_or_examples(message, expected):
    from stylist.policy import explicit_look_count
    count, evidence = explicit_look_count(message)
    assert count == expected
    assert not evidence or evidence in message


@pytest.mark.asyncio
async def test_explicit_count_survives_planner_omission():
    from stylist.models import Plan, SessionState
    from stylist.policy import interpret_task

    class Model:
        async def generate(self, *args):
            return Plan(mode='recommend')

    plan, _ = await interpret_task(Model(), {}, SessionState(), '从我的衣橱给我挑一套日常搭配')
    assert plan.requested_look_count == 1 and plan.look_count_evidence in '从我的衣橱给我挑一套日常搭配'


@pytest.mark.asyncio
async def test_styling_brief_uses_same_verified_memory_style_as_task(tmp_path):
    from scripts.dialogue_validation import DialogueUpstream
    from stylist.engine import Stylist
    from stylist.memory import MemoryBook, MemoryEntry
    from stylist.models import Change, ChatRequest, CompanionProfile, LookDraft, Plan
    from stylist.store import Store

    upstream = DialogueUpstream('wardrobe_only')
    store = Store(str(tmp_path / 'brief.db'))
    store.save_memory_book(await upstream.identity(), MemoryBook(entries=[
        MemoryEntry(id='style', content='我喜欢优雅风')]))

    class Model:
        async def generate(self, name, payload, result_type):
            if name == 'plan':
                return Plan(mode='recommend', memory_changes={'style': Change(value='优雅', evidence='我喜欢优雅风')},
                            changes={'weather_policy': Change(value='ignored', evidence='不考虑天气')})
            assert payload['task']['style'] == '优雅'
            assert payload['styling_brief']['effective_styles'] == ['优雅']
            return Draft(message='按现有衣物整理。', looks=[LookDraft(title='日常',
                         selected_keys=['user:101', 'user:102', 'user:103'], why=['白灰配色'], how=['自然穿着'])])

    await Stylist(Settings(), store, Model()).chat(upstream, ChatRequest(
        message='帮我搭一套，不考虑天气。', request_id='memory-brief',
        companion_profile=CompanionProfile(style_preferences=['休闲'])))


@pytest.mark.asyncio
async def test_parallel_detail_reads_wait_for_one_complete_mcp_catalog():
    from types import SimpleNamespace

    from stylist.upstream import MCPReads

    tool = SimpleNamespace(name='product.resolve', inputSchema={'type': 'object'}, outputSchema={'type': 'object'})

    class Session:
        discoveries = 0
        calls = 0

        async def list_tools(self, cursor=None):
            self.discoveries += 1
            await asyncio.sleep(.01)
            return SimpleNamespace(tools=[tool], nextCursor=None)

        async def call_tool(self, name, arguments, **kwargs):
            self.calls += 1
            return SimpleNamespace(structuredContent={'items': []}, isError=False)

    session = Session()
    reader = MCPReads(session)
    assert await asyncio.gather(*(reader.call('product.resolve', {}) for _ in range(4))) == [{'items': []}] * 4
    assert session.discoveries == 1 and session.calls == 4


@pytest.mark.asyncio
async def test_failed_discovery_does_not_cache_partial_catalog():
    from types import SimpleNamespace

    from stylist.upstream import MCPReads

    class Session:
        truncated = True

        async def list_tools(self, cursor=None):
            return SimpleNamespace(tools=[], nextCursor='more' if self.truncated else None)

    session = Session()
    reader = MCPReads(session)
    with pytest.raises(StylistError, match='tool_catalog_truncated'):
        await reader.discover()
    assert reader.tools is None
    session.truncated = False
    assert await reader.discover() == {}
