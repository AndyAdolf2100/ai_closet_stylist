"""Export current dialogue questions and acceptance criteria without model calls."""
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .companion_dialogues import SCENARIOS as COMPANION
from .dialogue_validation import EXPECTATIONS, SCENARIOS
from .evaluate_personas import CASES, SEQUENCE
from .exploratory_dialogues import EXPECTATIONS as EXP_EXPECTATIONS
from .exploratory_dialogues import SCENARIOS as EXPLORATION
from .preference_dialogues import SCENARIOS as PREFERENCES


def catalog():
    groups = []

    def add(name, rows, category, source, expectations):
        turns = []
        for index, (turn, message, chat) in enumerate(rows):
            expected = expectations.get(f'{name}/{turn}', {})
            turns.append({'turn': turn, 'index': index + 1, 'message': message,
                          'chat': chat, 'expected': expected})
        groups.append({'id': name, 'category': category, 'source': source, 'turns': turns})

    for case in CASES:
        add(case[0], [case], '日常与人设', 'scripts/evaluate_personas.py · CASES', {})
    add('sequence', SEQUENCE, '连续对话', 'scripts/evaluate_personas.py · SEQUENCE', {})
    for name, rows in SCENARIOS.items():
        category = '偏好与星座' if name in PREFERENCES else '称呼与角色' if name in COMPANION else '业务回归'
        source = {'偏好与星座': 'scripts/preference_dialogues.py / preference_coverage.py',
                  '称呼与角色': 'scripts/companion_dialogues.py', '业务回归': 'scripts/dialogue_validation.py'}[category]
        add(name, rows, category, source, EXPECTATIONS)
    for name, rows in EXPLORATION.items():
        add(name, rows, '天气与穿搭扩展', 'scripts/exploratory_dialogues.py', EXP_EXPECTATIONS)
    return {'generated_at': datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M 上海时间'),
            'groups': groups, 'rounds': sum(len(g['turns']) for g in groups),
            'rules': {name: Path('stylist/prompts', name).read_text() for name in [
                'persona_male_v1.md', 'persona_female_v1.md', 'companion_identity.md',
                'review_dialogue.md', 'review_preferences.md']}}


def render(output):
    data = catalog()
    template = Path(__file__).with_name('report_assets').joinpath('dialogue_catalog.html').read_text()
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(template.replace('__CATALOG_DATA__', payload))
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='var/dialogue-audit/dialogue-catalog.html')
    args = parser.parse_args()
    data = render(args.output)
    print(json.dumps({'scenarios': len(data['groups']), 'questions': data['rounds'],
                      'both_personas': data['rounds'] * 2, 'output': args.output}, ensure_ascii=False))
