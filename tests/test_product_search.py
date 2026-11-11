import pytest

from scripts.dialogue_validation import DialogueUpstream
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.models import ChatRequest, Plan
from stylist.product_search import ProductSearchSelection
from stylist.store import Store


class SearchModel:
    def __init__(self, keys=None, evidence=None):
        self.keys = ['user:104'] if keys is None else keys
        self.evidence = evidence
        self.calls = []

    async def generate(self, name, payload, result_type):
        self.calls.append((name, payload))
        if name == 'plan':
            return Plan(mode='recommend', product_search=True,
                        product_search_evidence=self.evidence or payload['message'])
        assert name == 'product_search', 'single lookup must not generate an outfit'
        return ProductSearchSelection(selected_keys=self.keys)


@pytest.mark.asyncio
@pytest.mark.parametrize('message', ['我想要一件黑色的衣服，帮我从衣柜里找找', '看看衣柜里有没有黑鞋', '找一双黑色乐福鞋', '帮我挑个黑色包', '给我看看我的黑色单品'])
async def test_search_returns_authoritative_cards_without_weather_or_outfits(tmp_path, message):
    model = SearchModel()
    upstream = DialogueUpstream('search')
    reply = await Stylist(Settings(), Store(str(tmp_path/'search.db')), model).chat(upstream,
        ChatRequest(message=message, request_id='single-search-test', new_clothes=True))
    assert reply.product_search and reply.delivery == 'advice' and not reply.looks
    assert [p.key for p in reply.product_results] == ['user:104']
    assert reply.product_results[0].title == '黑色平底乐福鞋'
    assert not reply.city_selection_required and not reply.weather
    assert 'forecast' not in upstream.calls and 'outfit.search-saved' not in upstream.calls
    assert len([c for c in upstream.calls if c == 'product.resolve']) == 1
    assert all(p.source == 'user' for p in reply.product_results)


@pytest.mark.asyncio
@pytest.mark.parametrize('unavailable', [False, True])
async def test_no_match_and_inventory_failure_are_different(tmp_path, unavailable):
    from stylist.errors import StylistError

    class Business(DialogueUpstream):
        async def get(self, path, params):
            if unavailable:
                raise StylistError('upstream_unavailable', 'fixture', 503)
            return await super().get(path, params)
    reply = await Stylist(Settings(), Store(str(tmp_path/'empty.db')), SearchModel(keys=[])).chat(
        Business('search'), ChatRequest(message='找件黑衣服', request_id='no-match-search'))
    assert reply.product_search and not reply.product_results and not reply.looks
    assert reply.reference_reason == ('unavailable' if unavailable else 'no_match')
    assert reply.wardrobe_gap is not unavailable


@pytest.mark.asyncio
async def test_invented_product_cannot_become_card(tmp_path):
    from stylist.errors import StylistError

    with pytest.raises(StylistError, match='product_search_invalid_selection'):
        await Stylist(Settings(), Store(str(tmp_path/'bad.db')), SearchModel(keys=['system:104'])).chat(
            DialogueUpstream('search'), ChatRequest(message='看看我的黑鞋', request_id='bad-search-result'))


@pytest.mark.asyncio
async def test_lookup_persists_card_history_and_idempotent_replay(tmp_path):
    model, upstream = SearchModel(), DialogueUpstream('search')
    engine = Stylist(Settings(), Store(str(tmp_path/'history.db')), model)
    request = ChatRequest(message='看看我的黑鞋', request_id='replay-search-result')
    first = await engine.chat(upstream, request)
    replay = await engine.chat(upstream, request)
    assert first == replay and len(model.calls) == 2
    saved = engine.store.history(await upstream.identity(), first.conversation_id)
    assert saved['messages'][0]['reply']['product_results'][0]['product_id'] == '104'


@pytest.mark.asyncio
async def test_lookup_keeps_existing_outfit_and_next_lookup_receives_results(tmp_path):
    import json

    from stylist.models import SessionState

    model, upstream = SearchModel(), DialogueUpstream('search')
    store = Store(str(tmp_path/'context.db'))
    engine = Stylist(Settings(), store, model)
    first = await engine.chat(upstream, ChatRequest(subject_product={'source': 'user', 'product_id': '104'},
        request_id='entry-before-lookup'))
    second = await engine.chat(upstream, ChatRequest(message='再看看黑鞋', request_id='search-after-entry',
        conversation_id=first.conversation_id, expected_version=1))
    with store.connection() as conn:
        row = conn.execute('SELECT state_json FROM stylist_sessions WHERE id=?', (first.conversation_id,)).fetchone()
    state = SessionState.model_validate_json(row['state_json'])
    assert state.looks == first.looks and state.task == first.task
    history = json.loads(state.messages[-1]['content'])
    assert history['product_search'] and history['product_results'][0]['product_id'] == '104'
    third = await engine.chat(upstream, ChatRequest(message='还有其他黑色的吗', request_id='search-followup',
        conversation_id=first.conversation_id, expected_version=second.version))
    assert third.product_search
    selector_payload = [payload for name, payload in model.calls if name == 'product_search'][-1]
    assert 'product_results' in selector_payload['history'][-1]['content']


@pytest.mark.asyncio
async def test_garment_scope_does_not_expand_black_clothes_to_shoes_and_bags(tmp_path):
    class Model(SearchModel):
        async def generate(self, name, payload, result_type):
            if name == 'product_search':
                return ProductSearchSelection(scope='garment', selected_keys=['user:101', 'user:104'])
            return await super().generate(name, payload, result_type)
    reply = await Stylist(Settings(), Store(str(tmp_path/'scope.db')), Model()).chat(
        DialogueUpstream('search'), ChatRequest(message='找件黑色衣服', request_id='garment-scope-test'))
    assert [p.product_id for p in reply.product_results] == ['101']


@pytest.mark.asyncio
async def test_lookup_never_reads_another_users_conversation(tmp_path):
    from stylist.errors import StylistError

    upstream = DialogueUpstream('search')
    engine = Stylist(Settings(), Store(str(tmp_path/'owner.db')), SearchModel())
    first = await engine.chat(upstream, ChatRequest(message='看看黑鞋', request_id='owner-a-search'))
    class Other(DialogueUpstream):
        async def identity(self):
            return 'synthetic-other-owner'
    other = Other('search')
    with pytest.raises(StylistError, match='conversation_not_found'):
        await engine.chat(other, ChatRequest(message='继续看看', request_id='owner-b-search',
            conversation_id=first.conversation_id, expected_version=1))
    assert not other.calls
