"""Optional outfit try-on: quote -> explicit confirmation -> one dispatch.

No language-model response can authorize this path. Uncertain dispatches never auto-replay.
"""
import hashlib
import json
import time
import uuid

from pydantic import Field

from .errors import StylistError
from .models import Model, ProductRef, SessionState
from .retrieval import resolve_products


class ImageQuoteRequest(Model):
    conversation_id: str = Field(pattern=r"^sty_[a-f0-9]{32}$")
    version: int = Field(ge=1)
    look_index: int = Field(default=0, ge=0, le=6)


class ImageConfirmRequest(Model):
    confirmed: bool


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def twin_fingerprint(overview):
    # Include actual portrait references, not only a mutable shared selection counter.
    return fingerprint({key: overview.get(key) for key in ["default_twin_key", "selection_version",
                                                          "custom_twin", "system_twins", "default_confirmed"]})


class ImageService:
    def __init__(self, store):
        self.store = store

    def context(self, owner, cid, version):
        with self.store.connection() as conn:
            row = conn.execute("SELECT * FROM stylist_sessions WHERE id=? AND owner_id=?", (cid, owner)).fetchone()
            if not row:
                raise StylistError("conversation_not_found", "找不到这条对话。", 404)
            if row["version"] != version or row["active_claim"]:
                raise StylistError("stale_version", "搭配正在变化，请刷新后重新查看费用。", 409)
            return SessionState.model_validate_json(row["state_json"])

    async def quote(self, upstream, request):
        owner = await upstream.identity()
        state = self.context(owner, request.conversation_id, request.version)
        if request.look_index >= len(state.looks) or not state.looks[request.look_index].items:
            raise StylistError("no_real_outfit", "文字参考尚未匹配真实衣物，不能直接生成试穿图。", 422)
        refs = [ProductRef(source=p.source, product_id=p.product_id) for p in state.looks[request.look_index].items]
        async with upstream.mcp() as mcp:
            overview = await mcp.call("digital_twin_overview", {})
            if not overview.get("default_twin_key") or not overview.get("default_confirmed"):
                raise StylistError("digital_twin_not_ready", "请先在现有 App 中选择并确认默认试穿形象，再回来试穿。", 409)
            cost = await mcp.call("digital_twin_tryon_quote", {})
            products = await resolve_products(mcp, refs)
            if {p.key for p in products} != {r.key for r in refs}:
                raise StylistError("outfit_changed", "部分衣物已不可用，请重新搭配。", 409)
            tools = await mcp.discover()
            names = ["save_recommended_outfit", "digital_twin_tryon"]
            if any(name not in tools for name in names):
                raise StylistError("image_tool_missing", "当前服务尚未开放这项试穿能力。")
            contract = fingerprint({name: tools[name].model_dump(mode="json") for name in names})
        action_id = "img_" + uuid.uuid4().hex
        snapshot = {"items": [r.model_dump() for r in refs], "points_cost": cost["points_cost"],
                    "twin": twin_fingerprint(overview), "contract": contract,
                    "scene": {"occasion": state.task.occasion, "style": state.task.style},
                    "title": state.looks[request.look_index].title,
                    "notices": ["确认后会将这套搭配保存到个人搭配库；系统商品会归入你的衣橱。",
                                "试穿图片用于视觉参考，不能保证实际尺码、面料和上身效果。"]}
        with self.store.connection() as conn:
            conn.execute("INSERT INTO stylist_image_actions(id,owner_id,conversation_id,version,quote_json,expires_at) VALUES(?,?,?,?,?,?)",
                         (action_id, owner, request.conversation_id, request.version,
                          json.dumps(snapshot, ensure_ascii=False), time.time() + 300))
        return {"action_id": action_id, "points_cost": cost["points_cost"], "title": snapshot["title"],
                "notices": snapshot["notices"], "expires_in_seconds": 300, "status": "quoted"}

    def get(self, owner, action_id):
        with self.store.connection() as conn:
            row = conn.execute("SELECT * FROM stylist_image_actions WHERE id=? AND owner_id=?", (action_id, owner)).fetchone()
            if not row:
                raise StylistError("image_action_not_found", "找不到当前账号的这次试穿。", 404)
            return dict(row)

    def status(self, owner, action_id):
        row = self.get(owner, action_id)
        return {"action_id": action_id, "status": row["status"],
                "result": json.loads(row["result_json"]) if row["result_json"] else None}

    def mark(self, owner, action_id, status, result=None):
        with self.store.connection() as conn:
            conn.execute("UPDATE stylist_image_actions SET status=?,result_json=? WHERE id=? AND owner_id=?",
                         (status, json.dumps(result, ensure_ascii=False) if result else None, action_id, owner))

    async def confirm(self, upstream, action_id, confirmed):
        owner = await upstream.identity()
        row = self.get(owner, action_id)
        if row["status"] == "completed":
            return self.status(owner, action_id)
        if not confirmed:
            with self.store.connection() as conn:
                conn.execute("UPDATE stylist_image_actions SET status='cancelled' WHERE id=? AND owner_id=? AND status='quoted'",
                             (action_id, owner))
            return self.status(owner, action_id)
        if row["status"] != "quoted":
            raise StylistError("image_already_submitted", "这次试穿已提交或已失效，请查看执行状态，不要重复生成。", 409)
        if row["expires_at"] < time.time():
            raise StylistError("image_quote_expired", "费用确认已过期，请重新查看本次费用。", 409)
        self.context(owner, row["conversation_id"], row["version"])
        snapshot = json.loads(row["quote_json"])
        async with upstream.mcp(image=True) as mcp:
            cost = await mcp.call("digital_twin_tryon_quote", {})
            overview = await mcp.call("digital_twin_overview", {})
            tools = await mcp.discover()
            names = ["save_recommended_outfit", "digital_twin_tryon"]
            contract = fingerprint({name: tools[name].model_dump(mode="json") for name in names if name in tools})
            if cost["points_cost"] != snapshot["points_cost"] or twin_fingerprint(overview) != snapshot["twin"] or contract != snapshot["contract"]:
                self.mark(owner, action_id, "expired")
                raise StylistError("image_quote_changed", "费用、形象或接口已变化，请重新查看费用并确认。", 409)
            # Claim before the first write, atomically checking the conversation is still current.
            with self.store.connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                current = conn.execute("SELECT version,active_claim FROM stylist_sessions WHERE id=? AND owner_id=?",
                                       (row["conversation_id"], owner)).fetchone()
                if not current or current["version"] != row["version"] or current["active_claim"]:
                    raise StylistError("stale_version", "搭配已变化，请重新确认当前搭配。", 409)
                changed = conn.execute("UPDATE stylist_image_actions SET status='executing' WHERE id=? AND owner_id=? AND status='quoted'",
                                       (action_id, owner))
                if changed.rowcount != 1:
                    raise StylistError("image_already_submitted", "这次试穿已经提交。", 409)
            try:
                saved = await mcp.commit_image("save_recommended_outfit", {"selection_id": action_id,
                    "items": [{"source": x["source"], "product_id": int(x["product_id"])} for x in snapshot["items"]]})
                result = await mcp.commit_image("digital_twin_tryon", {"outfit_id": saved["outfit_id"],
                    "idempotency_key": action_id, "scene": snapshot["scene"]})
                self.mark(owner, action_id, "completed", result)
            except BaseException:
                self.mark(owner, action_id, "unknown", {"message": "已尝试提交，上游最终状态需要核对。不会自动重复生成；请在现有 App 试穿记录中查看。"})
                raise StylistError("image_result_unknown", "尚未确认试穿最终状态，不会自动重复扣费生成，请查看现有 App 的试穿记录。") from None
        return self.status(owner, action_id)
