"""Explicit real-text routing check with synthetic wardrobe and temporary databases."""
import argparse
import asyncio
import json
import tempfile
from dataclasses import replace
from pathlib import Path

from scripts.dialogue_validation import DialogueUpstream
from stylist.config import Settings
from stylist.engine import Stylist
from stylist.llm import LanguageModel
from stylist.models import ChatRequest, SessionState
from stylist.policy import interpret_task
from stylist.store import Store

CASES = [
    ('我想要一件黑色的衣服，帮我从衣柜里找找', True, {'101'}),
    ('帮我看看衣柜里有没有黑鞋', True, {'104'}),
    ('找一双黑色乐福鞋', True, {'104'}),
    ('我的衣橱有哪些包可以选', True, {'106'}),
    ('帮我挑件通勤外套', True, {'105'}),
    ('我有白衬衫吗，找出来看看', True, {'107'}),
    ('看看我的帽子', True, set()),
    ('帮我从衣柜里挑一条灰裤子', True, {'102'}),
    ('用黑鞋搭一套，不考虑天气', False, set()),
    ('我想要一套黑色通勤搭配，不看天气', False, set()),
    ('黑色衣服怎么搭比较好，只讲原理', False, set()),
    ('找一件黑色上衣，再配裤子和鞋，不考虑天气', False, set()),
    ('给我找套西装，不考虑天气', False, set()),
    ('不用帮我找衣服，我就随便聊聊', False, set()),
    ('朋友说“帮我从衣柜找件黑衣服”，这句话有歧义吗', False, set()),
    ('想买件黑外套，先讲讲挑选原则，不查衣柜', False, set()),
]


def business():
    upstream = DialogueUpstream('product-search-live')
    upstream.products = [
        {'product_id': '101', 'class_name': '上衣', 'title': '黑色圆领短袖', 'color': '黑色', 'material': '棉'},
        {'product_id': '102', 'class_name': '裤子', 'title': '灰色长裤', 'color': '灰色', 'material': '棉'},
        {'product_id': '104', 'class_name': '鞋子', 'title': '黑色平底乐福鞋', 'color': '黑色', 'material': '皮革'},
        {'product_id': '105', 'class_name': '外套', 'title': '米白色通勤西装外套', 'color': '米白色', 'material': '棉'},
        {'product_id': '106', 'class_name': '包', 'title': '黑色手提包', 'color': '黑色', 'material': '皮革'},
        {'product_id': '107', 'class_name': '上衣', 'title': '白色长袖衬衫', 'color': '白色', 'material': '棉'},
    ]
    return upstream


async def run(output):
    settings = Settings.load()
    records, semaphore = [], asyncio.Semaphore(3)
    async with LanguageModel(settings).session() as llm:
        async def case(index, message, expected, allowed):
            async with semaphore:
                record = {'message': message, 'expected_product_search': expected}
                try:
                    if expected:
                        with tempfile.TemporaryDirectory(prefix='stylist-product-search-') as tmp:
                            engine = Stylist(replace(settings, checkpoint_database=''), Store(str(Path(tmp)/'qa.db')), llm)
                            upstream = business()
                            reply = await engine.chat(upstream, ChatRequest(message=message, request_id=f'product-search-live-{index:03}'))
                            ids = {p.product_id for p in reply.product_results}
                            record.update(reply=reply.model_dump(mode='json'), tools=upstream.calls,
                                passed=reply.product_search and not reply.looks and not reply.city_selection_required
                                       and ids <= allowed and bool(ids) == bool(allowed))
                    else:
                        plan, _ = await interpret_task(llm, {'message': message, 'history': [],
                            'current_task': {}, 'current_looks': [], 'now': '2026-11-11T16:00:00+08:00'}, SessionState(), message)
                        record.update(plan=plan.model_dump(mode='json'), passed=not plan.product_search)
                except Exception as exc:
                    record.update(passed=False, error_type=type(exc).__name__, error_code=getattr(exc, 'code', None))
                records.append((index, record))
                print(json.dumps({'case': index, 'passed': record['passed']}, ensure_ascii=False), flush=True)
        await asyncio.gather(*(case(i, *row) for i, row in enumerate(CASES)))
    result = {'scope': 'real text model, synthetic wardrobe, no real account or paid images',
              'model': settings.llm_model, 'cases': [r for _, r in sorted(records)]}
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({'passed': sum(r['passed'] for _, r in records), 'total': len(records)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--output', default='var/product-search-live/initial.json')
    args = parser.parse_args()
    if not args.live:
        parser.error('Use --live explicitly; this invokes the configured paid text model.')
    asyncio.run(run(args.output))
