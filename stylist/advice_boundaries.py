"""Narrow output checks for explicit text-only clothing limits and hypothetical facts."""
import re

from .models import Draft

PREFIX = '对话边界：'


def hypothetical_preference(message):
    return bool(re.match(r'\s*(?:假如|假设|如果)', message) and re.search(r'喜欢|讨厌|偏爱', message))


def piece_limit(message, task):
    if not task.owned_descriptions:
        return None
    match = re.search(r'(?:这|那|就|只用|只穿)\s*([1-7一二两三四五六七])\s*件', message)
    if not match:
        return None
    return {'一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7}.get(
        match[1], int(match[1]) if match[1].isdigit() else None)


def boundary_problems(draft, message, task):
    problems = []
    text = '\n'.join([draft.message, *draft.follow_ups])
    hypothetical = hypothetical_preference(message)
    if (hypothetical
            and not re.search(r'假如|假设|如果|若|这个前提|这种设定|不当作|不是确定', text)):
        problems.append(PREFIX + '本轮是假设，不得确认成用户真实偏好或穿着频次；用条件语气回答，不保存。')
    count = piece_limit(message, task)
    if not count:
        return problems
    owned = ' '.join(task.owned_descriptions)
    no_tuck = '不塞' in message or any('不塞' in s for s in task.preferences)
    fields = [('正文', draft.message), ('追问', '\n'.join(draft.follow_ups))]
    for i, look in enumerate(draft.looks):
        if len(look.pieces) > count:
            problems.append(PREFIX + f'第{i + 1}套超过指定{count}件，删除额外单品，不用附注把它算作例外。')
        fields.append((f'第{i + 1}套', '\n'.join([look.title, *look.pieces, *look.reference_pieces,
                                                *look.why, *look.how, *look.notes])))
    for label, value in fields:
        for clause in re.split(r'[，,。！？!?；;\n]', value):
            if (not re.search(r'打底|内搭|T恤', owned)
                    and re.search(r'(?:里面|内层).{0,12}(?:配|穿|加|搭).{0,15}(?:打底|内搭|T恤)|(?:需要|加|配|穿)一件.{0,8}(?:打底|内搭)', clause)
                    and not re.search(r'(?:不|别|无需|不要).{0,8}(?:加|穿|配|需要)', clause)):
                problems.append(PREFIX + f'{label}额外要求内搭；只能使用指定的{count}件，不能在穿法或备注中加第四件。')
            if (no_tuck and re.search(r'半塞|全塞|塞(?:进|入)|(?:前摆|下摆|衣角).{0,5}塞', clause)
                    and not re.search(r'不|别|无需|不要', clause)):
                problems.append(PREFIX + f'{label}违反不塞衣角要求，所有穿法都应保持下摆外放。')
    return list(dict.fromkeys(problems))


def boundary_fallback(draft, message, task):
    """Keep safe advice if model repair fails, without publishing a conflicting card."""
    if piece_limit(message, task):
        kept = [look for look in draft.looks
                if not boundary_problems(Draft(message='穿法', looks=[look]), message, task)]
        return Draft(message='只围绕你指定的单品来穿，不额外加衣物。先整理领口、袖口和下摆，再看整体比例。', looks=kept)
    return Draft(message='如果只是这个假设，我会把它当作本轮讨论的前提，不当作你的真实偏好，也不会写入手记。')
