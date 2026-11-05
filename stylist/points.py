"""Read the existing points ledger; never maintain or mutate a local balance."""
from decimal import Decimal, InvalidOperation

from .errors import StylistError


def available_points(payload):
    value = payload.get("total_available") if isinstance(payload, dict) else None
    try:
        if value is None or isinstance(value, bool):
            raise ValueError
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > 9_007_199_254_740_991:
            raise ValueError
    except (ValueError, InvalidOperation):
        raise StylistError("points_balance_invalid", "暂时无法确认可用积分，请稍后重试。", 502) from None
    return int(amount) if amount == amount.to_integral_value() else float(amount)


async def require_points(upstream, cost, code):
    # Called for each confirmed execution; no cache and no deduction here.
    try:
        required = Decimal(str(cost))
        if not required.is_finite() or required < 0:
            raise ValueError
    except (ValueError, InvalidOperation):
        raise StylistError("image_quote_changed", "费用暂时无法确认，请重新查看报价。", 409) from None
    balance = available_points(await upstream.get("/api/vip_center/points_detail"))
    if Decimal(str(balance)) < required:
        raise StylistError(code, "可用积分不足，这次的选择已保留，请补充后重新确认。", 409)
    return balance
