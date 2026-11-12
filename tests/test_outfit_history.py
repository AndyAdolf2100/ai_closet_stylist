from stylist.outfit_history import outfit_catalog


def test_cross_turn_numbering_and_product_entry_exclusion():
    rows = [{'reply': {'version': 1, 'looks': [{'title': '最初搭配', 'items': [{'product_id': 1}]}]}},
            {'reply': {'version': 2, 'product_entry': {}, 'looks': [{'title': '单品查看'}]}},
            {'reply': {'version': 3, 'looks': [{'title': '重新生成', 'items': [{'product_id': 2}]}]}}]
    catalog = outfit_catalog(rows)
    assert [(x['outfit_number'], x['version'], x['title']) for x in catalog] == [(1, 1, '最初搭配'), (2, 3, '重新生成')]
    assert catalog[0]['items'][0]['product_id'] == 1


def test_multi_look_turn_and_empty_history():
    assert outfit_catalog([]) == []
    assert [x['look_index'] for x in outfit_catalog([{'reply': {'looks': [{}, {}]}}])] == [0, 1]


def test_invalid_reference_never_substitutes_latest_outfit():
    from stylist.outfit_history import recalled_looks
    messages = [{'reply': {'version': 1, 'looks': [{'title': '原搭配'}]}}]
    assert recalled_looks(messages, [2]) == []
    assert recalled_looks(messages, [1, 2]) == []
    assert recalled_looks(messages, [1, 1]) == [{'title': '原搭配'}]
