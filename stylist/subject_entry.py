"""Read-only App entry payloads for product and saved-outfit detail pages."""

from collections.abc import Mapping

from .errors import StylistError
from .models import ProductRef, SavedOutfitRef


def _subject_error(code: str, message: str, status: int = 404) -> StylistError:
    return StylistError(code, message, status)


def _text(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _product_display(row: Mapping, subject: ProductRef) -> dict:
    status = row.get("beautify_status")
    status = status if type(status) is int and status in {0, 1, 2} else None
    return {
        "subject": subject.model_dump(mode="json"),
        "title": _text(row.get("title"), 500),
        "description": _text(row.get("features_desc") or row.get("description"), 2000),
        "image_url": _text(row.get("cutout_image") or row.get("original_image"), 2048),
        "class_name": _text(row.get("class_name"), 100),
        "secondary_class_name": _text(row.get("secondary_class_name"), 100),
        "color": _text(row.get("color"), 500),
        "style": _text(row.get("style"), 500),
        "beautify_status": status,
        "beautify_eligible": bool(subject.source == "user" and row.get("beautify_eligible") is True
                                   and status in {0, 2}),
        "available": True,
        "disabled_reason": None,
    }


async def resolve_product_entry(upstream, subject: ProductRef) -> dict:
    try:
        async with upstream.mcp() as mcp:
            result = await mcp.call("product.resolve", {"items": [subject.model_dump(mode="json")]})
    except StylistError:
        raise
    except Exception as exc:
        raise _subject_error("product_entry_unavailable", "单品读取暂时不可用，请稍后重试。", 503) from exc
    rows = result.get("items") if isinstance(result, dict) else None
    if not isinstance(rows, list):
        raise _subject_error("product_entry_invalid_result", "单品读取结果异常，请稍后重试。", 503)
    matches = [row for row in rows if isinstance(row, Mapping)
               and row.get("source") == subject.source
               and str(row.get("product_id")) == subject.product_id]
    if len(matches) != 1:
        raise _subject_error("product_entry_unavailable", "这件单品不存在或已不可用。")
    return _product_display(matches[0], subject)


def _outfit_item(row: Mapping) -> dict | None:
    if row.get("source") != "user" or not str(row.get("product_id") or "").isdigit():
        return None
    return {
        "source": "user",
        "product_id": str(row["product_id"]),
        "title": _text(row.get("title"), 500),
        "class_name": _text(row.get("class_name"), 100),
        "secondary_class_name": _text(row.get("secondary_class_name"), 100),
        "original_image": _text(row.get("original_image"), 2048),
        "cutout_image": _text(row.get("cutout_image"), 2048),
        "description": _text(row.get("description") or row.get("features_desc"), 2000),
        "gender": _text(row.get("gender"), 20),
        "color": _text(row.get("color"), 500),
        "material": _text(row.get("material"), 500),
    }


async def resolve_outfit_entry(upstream, subject: SavedOutfitRef) -> dict:
    try:
        async with upstream.mcp() as mcp:
            result = await mcp.call("outfit.resolve", {
                **subject.model_dump(mode="json"), "include_presentation": True,
            })
    except StylistError:
        raise
    except Exception as exc:
        raise _subject_error("outfit_entry_unavailable", "搭配读取暂时不可用，请稍后重试。", 503) from exc
    raw_outfit_id = result.get("outfit_id") if isinstance(result, dict) else None
    try:
        outfit_id = int(raw_outfit_id)
    except (TypeError, ValueError):
        outfit_id = 0
    if not isinstance(result, dict) or result.get("source") != subject.source or outfit_id != subject.outfit_id:
        raise _subject_error("outfit_entry_unavailable", "这套搭配不存在或已不可用。")
    raw_items = result.get("items")
    items = [_outfit_item(row) for row in raw_items] if isinstance(raw_items, list) else []
    items = [item for item in items if item is not None]
    if not items or len({item["product_id"] for item in items}) != len(items):
        raise _subject_error("outfit_entry_items_invalid", "这套搭配的单品信息不完整，请检查原搭配。")
    presentation = result.get("presentation")
    presentation = ({"canvas_image": _text(presentation.get("canvas_image"), 2048)}
                    if isinstance(presentation, Mapping) and presentation.get("canvas_image") else None)
    return {
        "subject": subject.model_dump(mode="json"),
        "title": _text(result.get("title"), 200),
        "description": _text(result.get("description"), 2000),
        "items": items,
        "presentation": presentation,
        "available": True,
        "disabled_reason": None,
    }
