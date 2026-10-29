from stylist.grounding import attribute_claim_problems, ground_attribute_fallback
from stylist.models import Draft, Product, Slot
from stylist.preferences import preferred_pool


def item(id, style, slot=Slot.TOP):
    return Product(source='user', product_id=str(id), slot=slot, styles=[style], original_image='https://example.invalid/photo.jpg')


def test_style_pool_applies_every_variant_preserves_photos_and_frozen_items():
    for target in ['简约', '休闲', '通勤', '温柔', '复古', '运动', '街头', '优雅']:
        wanted, other, shoes = item(1, target), item(2, '其他'), item(3, '', Slot.SHOES)
        pool = {p.key: p for p in [wanted, other, shoes]}
        selected, missing = preferred_pool(pool, [target])
        assert set(selected) == {wanted.key, shoes.key} and not missing
        assert selected[wanted.key].original_image == wanted.original_image
        retained, _ = preferred_pool(pool, [target], [other])
        assert other.key in retained


def test_unmatched_styles_remain_soft_and_multiple_choices_are_supported():
    a, b = item(1, '休闲'), item(2, '优雅')
    pool = {p.key: p for p in [a, b]}
    assert preferred_pool(pool, ['复古']) == (pool, ['复古'])
    assert preferred_pool(pool, ['休闲', '优雅']) == (pool, [])
    assert preferred_pool(pool, []) == (pool, [])


def test_comfort_guarantee_in_intro_is_rewritten_without_losing_outfit():
    draft = Draft(message='出门不用多想也舒服。')
    assert attribute_claim_problems(draft, {})
    fixed = ground_attribute_fallback(draft, {}, 'male_calm_v1')
    assert '也舒服' not in fixed.message and fixed.looks == draft.looks
    assert not attribute_claim_problems(Draft(message='先试穿，确认是否舒服再出门。'), {})


def test_current_style_phrase_matches_labels_without_false_missing_warning():
    p = item(1, '优雅')
    assert preferred_pool({p.key: p}, ['优雅风']) == ({p.key: p}, [])


def test_wardrobe_default_respects_explicit_and_historical_opt_outs():
    from stylist.preferences import wardrobe_requested
    assert wardrobe_requested('咨询一下，白衬衫怎么搭裤子？')
    assert not wardrobe_requested('不查衣橱，只给文字方案，怎么穿？')
    history = [{'role': 'user', 'content': '不查衣橱，只给文字方案。'}]
    assert not wardrobe_requested('那鞋子怎么搭？', history)
    assert wardrobe_requested('现在从衣橱选实际衣服', history)
