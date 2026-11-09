from contextlib import asynccontextmanager

import pytest

from stylist.config import Settings
from stylist.engine import Stylist
from stylist.models import ChatRequest
from stylist.store import Store


class NoModel:
    async def generate(self, *args, **kwargs):
        raise AssertionError("detail-page entry must not invoke the language model")


class EntryUpstream:
    authorization = "Bearer test"

    def __init__(self, result):
        self.result = result
        self.calls = []

    async def identity(self):
        self.calls.append("identity")
        return "1"

    @asynccontextmanager
    async def mcp(self):
        yield self

    async def call(self, name, args):
        self.calls.append((name, args))
        return self.result


@pytest.mark.asyncio
async def test_product_detail_entry_echoes_authoritative_product_without_model(tmp_path):
    upstream = EntryUpstream({"items": [{
        "source": "user", "product_id": "12", "title": "白衬衫",
        "class_name": "上衣", "secondary_class_name": "衬衫",
        "features_desc": "棉质", "original_image": "https://img/original.png",
        "cutout_image": "https://img/cutout.png", "color": "白色",
    }]})
    engine = Stylist(Settings(), Store(str(tmp_path / "entry.db")), NoModel())
    reply = await engine.chat(upstream, ChatRequest(
        subject_product={"source": "user", "product_id": "12"}, request_id="product-entry-001"))
    assert reply.product_entry["title"] == "白衬衫"
    assert reply.product_entry["image_url"] == "https://img/cutout.png"
    assert reply.subject_product.product_id == "12"
    assert reply.version == 1 and reply.conversation_id.startswith("sty_")
    assert upstream.calls[1][0] == "product.resolve"
    assert engine.store.history("1", reply.conversation_id)["messages"][0]["user"] == "打开单品：白衬衫"
    replay = await engine.chat(upstream, ChatRequest(
        subject_product={"source": "user", "product_id": "12"}, request_id="product-entry-001"))
    assert replay.conversation_id == reply.conversation_id
    assert len(upstream.calls) == 2


@pytest.mark.asyncio
async def test_saved_outfit_detail_entry_echoes_canvas_and_items(tmp_path):
    upstream = EntryUpstream({
        "source": "user", "outfit_id": 72, "title": "周末通勤",
        "description": "轻松穿法", "presentation": {"canvas_image": "https://img/canvas.png"},
        "items": [{"source": "user", "product_id": "12", "title": "白衬衫",
                   "class_name": "上衣", "secondary_class_name": "衬衫",
                   "original_image": "https://img/original.png", "cutout_image": "https://img/cutout.png",
                   "description": "棉质", "gender": "女", "color": "白色", "material": "棉"}],
    })
    engine = Stylist(Settings(), Store(str(tmp_path / "outfit-entry.db")), NoModel())
    reply = await engine.chat(upstream, ChatRequest(
        subject_outfit={"source": "user", "outfit_id": 72}, request_id="outfit-entry-001"))
    assert reply.outfit_entry["title"] == "周末通勤"
    assert reply.outfit_entry["presentation"]["canvas_image"].endswith("canvas.png")
    assert reply.looks[0].items[0].product_id == "12"
    assert reply.subject_outfit.outfit_id == 72


def test_detail_entry_requires_a_reference_when_message_is_empty():
    with pytest.raises(ValueError):
        ChatRequest(message="", request_id="entry-invalid")
