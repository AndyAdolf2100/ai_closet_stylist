"""Explicit live text-only semantic checks; no user data or business operations."""
import argparse
import asyncio
import json
import os
import shlex
from pathlib import Path
from stylist.config import Settings
from stylist.llm import LanguageModel
from stylist.models import Plan, Task
from .wardrobe_delete_dialogues import CASES, contextual_cases


async def run(output, contextual_only=False):
    for line in Path('config/deploy.env').read_text().splitlines():
        if '=' not in line or line.lstrip().startswith('#'):
            continue
        key, value = line.split('=', 1)
        if key in {'STYLIST_LLM_URL', 'STYLIST_LLM_MODEL', 'STYLIST_LLM_KEY'}:
            parts = shlex.split(value)
            os.environ[key] = parts[0] if parts else ''
    settings = Settings.load()
    model = LanguageModel(settings)
    rows = []
    scenarios = [{'message': message, 'expected': expected} for message, expected in CASES] + contextual_cases()
    if contextual_only:
        scenarios = contextual_cases()
    default_history = [{'role': 'user', 'content': '看看这件白衬衫'},
                       {'role': 'assistant', 'content': json.dumps({'product_entry': {'title': '白衬衫'}, 'product_search': True})}]
    semaphore = asyncio.Semaphore(3)
    async def check(case):
        async with semaphore:
            message, expected = case['message'], case['expected']
            plan = await model.generate('plan', {'message': message, 'current_task': Task().model_dump(mode='json'),
                'current_mode': 'consult', 'history': case.get('history', default_history),
                'current_looks': [], 'outfit_history': []}, Plan)
            evidence_valid = expected is None or bool(plan.wardrobe_delete_evidence.strip() and plan.wardrobe_delete_evidence.strip() in message)
            scope_valid = expected is None or plan.wardrobe_delete_scope == case.get('scope', 'user')
            row = {'message': message, 'expected': expected, 'actual': plan.wardrobe_delete_intent,
                   'scope': plan.wardrobe_delete_scope,
                   'passed': plan.wardrobe_delete_intent == expected and evidence_valid and scope_valid,
                   'plan': plan.model_dump(mode='json')}
            print(json.dumps({key: value for key, value in row.items() if key != 'plan'}, ensure_ascii=False), flush=True)
            return row
    async with model.session():
        rows = await asyncio.gather(*(check(case) for case in scenarios))
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'model': settings.llm_model, 'kind': 'real_text_model_synthetic_context_no_business_calls', 'results': rows}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--output', default='var/dialogue-qa/wardrobe-delete-live.json')
    parser.add_argument('--contextual-only', action='store_true')
    args = parser.parse_args()
    asyncio.run(run(args.output, args.contextual_only))
