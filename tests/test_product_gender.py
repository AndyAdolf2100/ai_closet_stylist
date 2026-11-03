"""Garment audience labels survive retrieval and constrain every owned-outfit entry point."""
import json
from contextlib import asynccontextmanager

import pytest

from stylist.config import Settings
from stylist.engine import Stylist
from stylist.errors import StylistError
from stylist.models import (
    Change,
    ChatRequest,
    CompanionProfile,
    Draft,
    Look,
    LookDraft,
    Plan,
    Product,
    Reply,
    Slot,
    Task,
)
from stylist.policy import GENDER_PREFIX, suitability, validate_look
from stylist.retrieval import from_row, resolve_products, retrieve, saved_candidates
from stylist.store import Store


@pytest.mark.parametrize('raw,expected', [
    ('1', '男'), (1, '男'), ('男', '男'), (' male ', '男'),
    ('2', '女'), (2, '女'), ('女', '女'), ('female', '女'),
    ('3', '男女同款'), (3, '男女同款'), ('男女同款', '男女同款'), ('通用', '男女同款'),
    ('unisex', '男女同款'), (None, None), ('', None), ('0', None), (0, None),
    ('未知', None), ('4', None), (True, None),
])
def test_normalize_raw_and_resolved_gender_without_turning_unknown_into_unisex(raw, expected):
    item = from_row({'user_product_id': '1', 'class_name': '上衣', 'gender': raw}, 'user')
    assert item.gender == expected
    assert Product.model_validate_json(item.model_dump_json()).gender == expected


def test_authoritative_unknown_overrides_old_extras_and_legacy_results_still_load():
    item = from_row({'user_product_id': '1', 'class_name': '上衣', 'gender': ''}, 'user', {'gender': '男'})
    assert item.gender is None
    assert Product(source='user', product_id='1', slot='top').gender is None


@pytest.mark.parametrize('target,declared,title,allowed', [
    ('男', '女', '普通衬衫', False), ('女', '男', '普通衬衫', False),
    ('男', '男', '白色衬衫', True), ('女', '女', '白色衬衫', True),
    ('男', '男女同款', '男女同款运动鞋', True), ('女', '男女同款', '男女同款运动鞋', True),
    ('男', None, '白色长袖衬衫女2026春款', False), ('女', None, '男士白衬衫', False),
    ('男', '男', '女士白衬衫', False), ('女', '女', '男装白衬衫', False),
    ('男', '男女同款', '女士白衬衫', False), ('男', None, '女衬衫', False),
    ('男', None, 'Women’s white shirt', False), ('女', None, "Men's white shirt", False),
    ('男', None, '白色长袖衬衫女', False), ('女', None, '白色长袖衬衫男', False),
    ('男', None, '普通长袖衬衫', True), ('男', '男', '女神同款配色衬衫', True),
    ('男', '男', '宽松粉色长裙', True),  # Category/color alone is not gender evidence.
    (None, '女', '女士白衬衫', True),
])
def test_gender_suitability_uses_labels_and_explicit_titles_not_stereotypes(target, declared, title, allowed):
    product = Product(source='user', product_id='1', slot='top', gender=declared, title=title)
    reasons, warnings = suitability(product, Task(gender=target))
    assert (not reasons) is allowed
    if not allowed:
        assert reasons[0].startswith(GENDER_PREFIX)
    if allowed and declared is None and target:
        assert any('未标注衣物性别' in text for text in warnings)


def row(pid, title, category, gender):
    return {'product_id': str(pid), 'user_product_id': str(pid), 'source': 'user', 'title': title,
            'class_name': category, 'gender': gender, 'color': '白色', 'material': '棉'}


class Wardrobe:
    def __init__(self):
        self.owner, self.calls = 'synthetic-gender-owner', []
        self.rows = [row(501, '普通白衬衫', '上衣', '0'), row(201, '女款白衬衫', '上衣', '2'),
                     row(101, '男士白衬衫', '上衣', '1'), row(301, '通用长裤', '裤子', '3'),
                     row(401, '男女同款平底运动鞋', '鞋子', '3'),
                     row(601, '女士长袖衬衫', '上衣', '1'), row(701, '女款短袖衬衫', '上衣', '')]
        self.saved_ids = []

    async def identity(self):
        return self.owner

    async def get(self, path, params):
        assert path == '/api/user_product/quick_edit_list'
        self.calls.append(path)
        return {'list': self.rows, 'pagination': {'total': len(self.rows)}}

    @asynccontextmanager
    async def mcp(self):
        yield self

    async def call(self, name, args):
        self.calls.append(name)
        if name == 'product.resolve':
            ids = {r['product_id'] for r in args['items']}
            assert all(r['source'] == 'user' for r in args['items'])
            return {'items': [dict(r) for r in self.rows if r['product_id'] in ids]}
        if name == 'outfit.search-saved':
            return {'matches': [{'outfit_id': '1'}] if self.saved_ids else []}
        if name == 'outfit.resolve':
            return {'items': [dict(r) for r in self.rows if r['product_id'] in self.saved_ids]}
        raise AssertionError('Unexpected call: ' + name)


async def test_personal_retrieval_filters_conflicts_and_ranks_verified_gender_before_unknown():
    api = Wardrobe()
    pool, warnings, rejected = await retrieve(api, api, Task(gender='男'), '通勤')
    assert set(pool) == {'user:101', 'user:301', 'user:401', 'user:501'}
    assert list(pool).index('user:101') < list(pool).index('user:501')
    assert sum(rejected.values()) == 3
    assert pool['user:501'].gender is None and pool['user:501'].warnings
    assert all('kb_search' not in call for call in api.calls)
    assert warnings == []


async def test_saved_outfits_and_resolve_keep_authoritative_gender():
    api = Wardrobe()
    api.saved_ids = ['101', '201', '401']
    saved = await saved_candidates(api, Task(gender='男'))
    assert {p.key for p in saved} == {'user:101', 'user:401'}
    resolved = await resolve_products(api, [Product(source='user', product_id='201', slot='top')])
    assert resolved[0].gender == '女'


class Model:
    def __init__(self, keys=None, *, target=None, mode='recommend'):
        self.keys, self.target, self.mode, self.payloads = keys, target, mode, []

    async def generate(self, name, payload, result_type):
        self.payloads.append((name, payload))
        if name == 'plan':
            changes = {'weather_policy': Change(value='ignored', evidence='不考虑天气')}
            if self.target:
                changes['gender'] = Change(value=self.target, evidence=self.target + '装')
            return Plan(mode=self.mode, changes=changes, use_profile_gender=self.target is None,
                        replace_slots=[Slot.SHOES] if self.mode == 'modify' else [])
        if not self.keys:
            return Draft(message='本次候选未匹配穿衣要求，先给文字参考。')
        return Draft(message='按本轮对象选择衣橱单品。', looks=[LookDraft(title='通勤搭配',
            selected_keys=self.keys, why=['配色简洁'], how=['自然垂放'])])


@pytest.mark.parametrize('persona', ['male_calm_v1', 'male_artistic_v1', 'male_confident_v1',
                                    'female_sweet_v1', 'female_warm_v1', 'female_regal_v1'])
async def test_male_profile_reaches_candidates_and_selected_items_for_every_companion(tmp_path, persona):
    api, model = Wardrobe(), Model(['user:101', 'user:301', 'user:401'])
    result = await Stylist(Settings(), Store(str(tmp_path/'state.db')), model).chat(api, ChatRequest(
        message='帮我搭一套通勤装，不考虑天气', request_id='gender-profile-outfit',
        companion_profile=CompanionProfile(user_gender='男', assistant_persona=persona)))
    assert result.task.gender == '男' and result.delivery == 'outfit'
    payload = next(p for name, p in model.payloads if name == 'style')
    assert {p['key'] for p in payload['candidates']} == {'user:101', 'user:301', 'user:401', 'user:501'}
    assert all(p.gender in {'男', '男女同款'} for p in result.looks[0].items)
    assert not any('tryon' in call or 'generate' in call for call in api.calls)


@pytest.mark.parametrize('profile_gender,target,key', [('男', '女', 'user:201'), ('女', '男', 'user:101')])
async def test_explicit_outfit_target_overrides_profile(tmp_path, profile_gender, target, key):
    model = Model([key, 'user:301', 'user:401'], target=target)
    reply = await Stylist(Settings(), Store(str(tmp_path/'state.db')), model).chat(Wardrobe(), ChatRequest(
        message=f'这次给朋友搭{target}装，不考虑天气', request_id='gender-explicit-target',
        companion_profile=CompanionProfile(user_gender=profile_gender, assistant_persona='male_calm_v1')))
    assert reply.task.gender == target and reply.looks[0].items[0].gender == target


async def test_all_opposite_candidates_are_no_match_not_an_empty_wardrobe(tmp_path):
    api, model = Wardrobe(), Model()
    api.rows = [r for r in api.rows if r['product_id'] == '201']
    reply = await Stylist(Settings(), Store(str(tmp_path/'state.db')), model).chat(api, ChatRequest(
        message='搭一套，不考虑天气', request_id='gender-no-match', companion_profile=CompanionProfile(user_gender='男')))
    assert reply.delivery == 'concept' and not reply.looks
    assert any('不代表整个衣橱为空' in warning for warning in reply.warnings)
    assert next(p for name, p in model.payloads if name == 'style')['candidates'] == []


async def seed(store, api):
    req = ChatRequest(message='原来的通勤搭配', request_id='gender-seed-outfit')
    cid, claim, state, _ = store.reserve(api.owner, req)
    state.task = Task(gender='男', weather_policy='ignored', no_heels=True)
    state.mode = 'recommend'
    # Legacy results have no garment gender. Only the new authoritative read may establish it.
    state.looks = [Look(title='原搭配', items=[Product(source='user', product_id='101', slot='top', title='白衬衫'),
        Product(source='user', product_id='301', slot='bottom'),
        Product(source='user', product_id='401', slot='shoes', title='平底运动鞋')])]
    store.finish(api.owner, req, claim, state, Reply(
        conversation_id=cid, version=1, mode='recommend', delivery='outfit', message='原搭配', task=state.task, looks=state.looks))
    return cid


async def test_old_frozen_piece_with_fresh_opposite_label_stops_local_edit_without_rewriting_history(tmp_path):
    api, store = Wardrobe(), Store(str(tmp_path/'state.db'))
    cid = await seed(store, api)
    api.rows[2]['gender'], api.rows[2]['title'] = '2', '女款白衬衫'
    model = Model(['user:101', 'user:301', 'user:401'], mode='modify')
    with pytest.raises(StylistError, match='frozen_gender_conflict'):
        await Stylist(Settings(), store, model).chat(api, ChatRequest(message='只换鞋，不考虑天气',
            conversation_id=cid, expected_version=1, request_id='gender-frozen-conflict'))
    assert [name for name, _ in model.payloads] == ['plan']
    assert store.history(api.owner, cid)['version'] == 1


async def test_uploaded_opposite_piece_cannot_be_forced_into_male_outfit(tmp_path):
    api, store = Wardrobe(), Store(str(tmp_path/'state.db'))
    action = 'med_' + 'a'*32
    with store.connection() as conn:
        conn.execute('INSERT INTO stylist_media_actions(id,owner_id,kind,digest,status,snapshot_json,result_json) VALUES(?,?,?,?,?,?,?)',
            (action, api.owner, 'garment', 'synthetic', 'completed', '{}', json.dumps({'user_product_id':'201'})))
    model = Model(['user:101', 'user:301', 'user:401'])
    reply = await Stylist(Settings(), store, model).chat(api, ChatRequest(message='用这件搭一套，不考虑天气',
        request_id='gender-upload-anchor', upload_action_id=action, companion_profile=CompanionProfile(user_gender='男')))
    assert all(p.product_id != '201' for p in reply.looks[0].items)
    assert any('刚上传的单品与本轮要求冲突' in warning for warning in reply.warnings)


def test_final_validation_cannot_select_an_opposite_gender_item_even_if_a_pool_is_bypassed():
    item = Product(source='user', product_id='201', slot='top', gender='女')
    assert any(p.startswith(GENDER_PREFIX) for p in validate_look([item.key], {item.key:item},
        Task(gender='男'), set(), require_complete=False))


async def test_historical_regeneration_reads_fresh_gender_and_does_not_reuse_female_source(tmp_path):
    api, store = Wardrobe(), Store(str(tmp_path/'state.db'))
    cid = await seed(store, api)
    # The archived top is now authoritatively female; another verified male top is available.
    api.rows[2]['gender'], api.rows[2]['title'] = '2', '女款旧衬衫'
    api.rows.append(row(111, '男士蓝色长袖衬衫', '上衣', '1'))
    model = Model(['user:111','user:301','user:401'])
    reply = await Stylist(Settings(), store, model).chat(api, ChatRequest(message='重新生成穿搭',
        regenerate_outfit=True, regenerate_from_version=1, selected_look_index=0,
        conversation_id=cid, expected_version=1, request_id='gender-old-regeneration'))
    assert reply.task.gender == '男' and reply.looks[0].items[0].gender == '男'
    assert all(p.product_id != '101' for p in reply.looks[0].items)
    assert [name for name, _ in model.payloads] == ['style']
    assert store.history(api.owner, cid)['messages'][0]['reply']['looks'][0]['items'][0]['gender'] is None


async def test_valid_frozen_pieces_are_refreshed_with_gender_and_remain_frozen(tmp_path):
    api, store = Wardrobe(), Store(str(tmp_path/'state.db'))
    cid = await seed(store, api)
    api.rows.append(row(402, '男女同款平底帆布鞋', '鞋子', '3'))
    model = Model(['user:101','user:301','user:402'], mode='modify')
    reply = await Stylist(Settings(), store, model).chat(api, ChatRequest(message='只换鞋，不考虑天气',
        conversation_id=cid, expected_version=1, request_id='gender-frozen-valid'))
    assert {p.product_id for p in reply.looks[0].items} == {'101','301','402'}
    assert reply.looks[0].items[0].gender == '男'


def test_qa_checker_audits_actual_garments_even_when_task_gender_is_correct():
    from scripts.dialogue_validation import check_reply
    wrong = Product(source='user',product_id='1',slot='top',gender='女')
    reply = Reply(conversation_id='sty_'+'a'*32, version=1, mode='recommend', delivery='outfit',
        message='男装搭配',task=Task(gender='男'),looks=[Look(title='搭配',items=[wrong])])
    expected = {'garment_gender':'男','require_gender_labels':True}
    assert 'garment_gender_mismatch' in check_reply(reply, expected, [])
    reply.looks[0].items[0] = wrong.model_copy(update={'gender':None})
    assert 'garment_gender_unknown' in check_reply(reply, expected, [])
