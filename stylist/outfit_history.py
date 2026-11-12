"""Stable, conversation-wide outfit references for dialogue grounding."""
def outfit_catalog(messages):
    result = []
    for turn in messages:
        reply = turn.get('reply') or {}
        if reply.get('historical_outfit_replay') or reply.get('saved_outfit_search'):
            continue
        if reply.get('product_entry') is not None or reply.get('outfit_entry') is not None:
            continue
        for index, look in enumerate(reply.get('looks') or []):
            if not isinstance(look, dict):
                continue
            result.append({'outfit_number': len(result) + 1, 'version': reply.get('version'),
                           'look_index': index, 'title': look.get('title'),
                           'pieces': look.get('pieces'), 'how': look.get('how'),
                           'items': [{key: item.get(key) for key in
                                      ('source', 'product_id', 'slot', 'name', 'color', 'category')}
                                     for item in look.get('items', []) if isinstance(item, dict)]})
    return result


def recalled_looks(messages, numbers):
    """Resolve model-selected semantic references only against owned saved replies."""
    catalog = outfit_catalog(messages)
    by_number = {row['outfit_number']: row for row in catalog}
    if not numbers or any(number not in by_number for number in numbers):
        return []
    replies = {turn['reply'].get('version'): turn['reply'] for turn in messages}
    return [replies[by_number[number]['version']]['looks'][by_number[number]['look_index']]
            for number in dict.fromkeys(numbers)]
