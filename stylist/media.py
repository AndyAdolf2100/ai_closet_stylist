"""User-initiated wardrobe/twin writes, outside the replayable conversation graph.

Only hashes, owned task references and business results persist. Photo bytes and
authorization headers never enter the task store. Unknown writes never auto-replay.
"""
import base64
import binascii
import hashlib
import json
import time
from typing import Literal

from pydantic import Field, StrictBool

from .errors import StylistError
from .models import Model


class UploadInput(Model):
    request_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    kind: Literal["garment", "person"]
    image_data: str = Field(min_length=20, max_length=13981039)
    confirmed: StrictBool


class GenerationInput(Model):
    request_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    hat_action: Literal["none", "keep", "remove"] = "none"
    hair_description: str = Field(default="", max_length=500)


class ConfirmInput(Model):
    confirmed: StrictBool


class TwinSelection(Model):
    twin_key: str = Field(min_length=1, max_length=32)
    expected_version: int = Field(ge=0)


class TwinCandidate(Model):
    task_id: str = Field(min_length=1, max_length=32, pattern=r"^[0-9]+$")
    expected_version: int = Field(ge=0)


class TwinGender(Model):
    gender: Literal["男", "女"]
    expected_version: int = Field(ge=0)


class TwinBodyProfile(Model):
    expected_version: int = Field(ge=0)
    height_cm: float | None = Field(default=None, gt=0, le=300, allow_inf_nan=False)
    weight_kg: float | None = Field(default=None, gt=0, le=500, allow_inf_nan=False)
    body_description: str | None = Field(default=None, max_length=1000)
    skin_tone: str | None = Field(default=None, max_length=64)
    skin_description: str | None = Field(default=None, max_length=500)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def image_digest(value):
    try:
        header, encoded = value.split(",", 1)
        raw = base64.b64decode(encoded, validate=True)
        valid = {"data:image/png;base64": raw.startswith(b"\x89PNG\r\n\x1a\n"),
                 "data:image/jpeg;base64": raw.startswith(b"\xff\xd8\xff"),
                 "data:image/webp;base64": raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"}
        if not 16 <= len(raw) <= 10 * 1024 * 1024 or not valid.get(header):
            raise ValueError()
        return hashlib.sha256(raw).hexdigest()
    except (ValueError, binascii.Error) as exc:
        raise StylistError("invalid_upload", "请选择10MB以内的JPG、PNG或WebP图片。", 422) from exc


class MediaActions:
    def __init__(self, store):
        self.store = store

    def get(self, owner, action):
        with self.store.connection() as conn:
            row = conn.execute("SELECT * FROM stylist_media_actions WHERE id=? AND owner_id=?",
                               (action, owner)).fetchone()
        if not row:
            raise StylistError("media_not_found", "找不到当前账号的这次操作。", 404)
        return dict(row)

    def view(self, row):
        return {"action_id": row["id"], "kind": row["kind"], "status": row["status"],
                "result": json.loads(row["result_json"] or "{}"), "created_at": row["created_at"]}

    def list(self, owner):
        with self.store.connection() as conn:
            rows = conn.execute("SELECT * FROM stylist_media_actions WHERE owner_id=? ORDER BY created_at DESC,id DESC LIMIT 30",
                                (owner,)).fetchall()
        return [self.view(dict(row)) for row in rows]

    def reserve(self, owner, request_id, kind, fingerprint, snapshot, status="executing"):
        action = "med_" + digest([owner, kind, request_id])[:32]
        with self.store.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM stylist_media_actions WHERE id=? AND owner_id=?", (action, owner)).fetchone()
            if row:
                if row["digest"] != fingerprint:
                    raise StylistError("idempotency_conflict", "同一操作编号不能用于不同的图片或选择。", 409)
                return dict(row), False
            conn.execute("INSERT INTO stylist_media_actions(id,owner_id,kind,digest,status,snapshot_json) VALUES(?,?,?,?,?,?)",
                         (action, owner, kind, fingerprint, status, json.dumps(snapshot, ensure_ascii=False)))
        return self.get(owner, action), True

    def save(self, owner, action, result, status=None):
        status = status or result.get("status", "unknown")
        if status not in {"processing", "completed", "failed", "unknown", "quoted", "cancelled", "expired"}:
            status = "unknown"
        with self.store.connection() as conn:
            conn.execute("UPDATE stylist_media_actions SET status=?,result_json=? WHERE id=? AND owner_id=?",
                         (status, json.dumps(result, ensure_ascii=False), action, owner))
        return self.view(self.get(owner, action))

    def failed_dispatch(self, owner, action, exc):
        # Typed rejections establish non-acceptance; transport loss does not.
        rejected = {"product_upload_capacity_exhausted", "digital_twin_points_insufficient",
                    "tool_input_invalid", "tool_missing", "invalid_arguments"}
        expired = {"digital_twin_price_changed", "digital_twin_check_expired"}
        code = getattr(exc, "code", "")
        state = "failed" if code in rejected else ("expired" if code in expired else "unknown")
        message = exc.message if state != "unknown" else "提交结果待核对，不会自动重复上传或扣费。"
        return self.save(owner, action, {"message": message, "error_code": code}, state)

    async def upload(self, upstream, request):
        owner = await upstream.identity()
        if request.confirmed is not True:
            return {"status": "cancelled"}
        hashed = image_digest(request.image_data)
        row, claimed = self.reserve(owner, request.request_id, request.kind, hashed, {})
        if not claimed:
            return self.view(row)
        tool = "product_add" if request.kind == "garment" else "digital_twin_photo_check"
        try:
            async with upstream.mcp(image=True) as mcp:
                result = await mcp.commit_media(tool, {"image_data": request.image_data, "idempotency_key": row["id"]})
            return self.save(owner, row["id"], result)
        except BaseException as exc:
            self.failed_dispatch(owner, row["id"], exc)
            raise

    async def refresh(self, upstream, action):
        owner = await upstream.identity()
        row = self.get(owner, action)
        result = json.loads(row["result_json"] or "{}")
        if row["status"] not in {"processing", "unknown", "executing"}:
            return self.view(row)
        specs = {"garment": ("product_upload_status", "task_id"),
                 "person": ("digital_twin_photo_check_status", "check_id"),
                 "generation": ("digital_twin_generation_status", "task_id")}
        tool, key = specs[row["kind"]]
        if not result.get(key):
            # Reconcile a lost response by its original, owner-scoped request key.
            if row["kind"] == "garment":
                async with upstream.mcp() as mcp:
                    fresh = await mcp.call("product_upload_receipt", {"idempotency_key": action})
                return self.save(owner, action, fresh)
            if row["kind"] == "generation":
                overview = await upstream.get("/api/digital_twin/overview")
                candidates = [overview.get("pending_task"), overview.get("latest_task")]
                match = next((p for p in candidates if p and p.get("request_id") == action), None)
                if match:
                    result[key] = str(match["task_id"])
            if not result.get(key):
                # A missing task cannot prove a write was rejected; never resubmit.
                return self.view(row)
        async with upstream.mcp() as mcp:
            fresh = await mcp.call(tool, {key: str(result[key])})
        return self.save(owner, action, fresh)

    async def overview(self, upstream):
        await upstream.identity()
        # HTTP projection includes actual balance, generation price and profile prerequisite.
        return await upstream.get("/api/digital_twin/overview")

    async def generation_quote(self, upstream, photo_action, request):
        owner = await upstream.identity()
        row = self.get(owner, photo_action)
        if row["kind"] != "person":
            raise StylistError("photo_check_required", "请先上传并检查人物照片。", 409)
        refreshed = await self.refresh(upstream, photo_action)
        check = refreshed["result"]
        async with upstream.mcp() as mcp:
            if check.get("check_id"):
                check = await mcp.call("digital_twin_photo_check_status", {"check_id": str(check["check_id"])})
        if check.get("status") != "completed" or request.hat_action not in check.get("allowed_hat_actions", []):
            raise StylistError("photo_check_required", "照片尚未通过检查，或需要先选择帽子处理方式。", 409)
        cost = check.get("generation_cost_points")
        if type(cost) is not int or cost < 0:
            raise StylistError("quote_unavailable", "暂时无法读取生成费用，请稍后重试。", 502)
        selection = {"check_id": str(check["check_id"]), "hat_action": request.hat_action,
                     "hair_description": request.hair_description}
        snapshot = {**selection, "expected_cost_points": cost, "expires_at": time.time() + 300}
        quoted, _ = self.reserve(owner, request.request_id, "generation", digest(selection), snapshot, "quoted")
        return {**self.view(quoted), "points_cost": json.loads(quoted["snapshot_json"])["expected_cost_points"],
                "hat_action": request.hat_action}

    async def confirm_generation(self, upstream, action, confirmed):
        owner = await upstream.identity()
        row = self.get(owner, action)
        if row["kind"] != "generation":
            raise StylistError("invalid_media_action", "这次操作不是人物生成报价。", 422)
        if row["status"] != "quoted":
            return self.view(row)
        if not confirmed:
            with self.store.connection() as conn:
                conn.execute("UPDATE stylist_media_actions SET status='cancelled' WHERE id=? AND owner_id=? AND status='quoted'",
                             (action, owner))
            return self.view(self.get(owner, action))
        snapshot = json.loads(row["snapshot_json"])
        if time.time() > snapshot["expires_at"]:
            self.save(owner, action, {}, "expired")
            raise StylistError("image_quote_expired", "报价已过期，请重新查看费用。", 409)
        async with upstream.mcp(image=True) as mcp:
            check = await mcp.call("digital_twin_photo_check_status", {"check_id": snapshot["check_id"]})
            if (check.get("status") != "completed"
                    or check.get("generation_cost_points") != snapshot["expected_cost_points"]
                    or snapshot["hat_action"] not in check.get("allowed_hat_actions", [])):
                self.save(owner, action, {}, "expired")
                raise StylistError("image_quote_changed", "照片状态或费用已变化，请重新查看并确认。", 409)
            with self.store.connection() as conn:
                changed = conn.execute("UPDATE stylist_media_actions SET status='executing' WHERE id=? AND owner_id=? AND status='quoted'",
                                       (action, owner))
                claimed = changed.rowcount == 1
            if not claimed:
                return self.view(self.get(owner, action))
            try:
                result = await mcp.commit_media("digital_twin_generate", {k: v for k, v in
                    {**snapshot, "request_id": action}.items() if k != "expires_at"})
                return self.save(owner, action, result)
            except BaseException as exc:
                self.failed_dispatch(owner, action, exc)
                raise

    async def select(self, upstream, request):
        await upstream.identity()
        async with upstream.mcp() as mcp:
            overview = await mcp.call("digital_twin_overview", {})
            keys = [x["twin_key"] for x in overview.get("system_twins", [])]
            if overview.get("custom_twin"):
                keys.append("custom")
            if request.twin_key not in keys or request.expected_version != overview["selection_version"]:
                raise StylistError("twin_changed", "形象已更新，请重新选择。", 409)
            return await mcp.commit_media("digital_twin_set_default", {**request.model_dump(),
                "idempotency_key": "select_" + digest(request.model_dump())[:32]})

    async def use_candidate(self, upstream, request):
        owner = await upstream.identity()
        async with upstream.mcp() as mcp:
            overview = await mcp.call("digital_twin_overview", {})
            pending = overview.get("pending_task") or {}
            if (str(pending.get("task_id")) != request.task_id or not pending.get("can_confirm")
                    or overview.get("selection_version") != request.expected_version):
                raise StylistError("twin_changed", "这个候选暂时不能确认，请刷新查看当前形象。", 409)
            return await mcp.commit_media("digital_twin_confirm", {**request.model_dump(),
                "idempotency_key": "use_" + digest([owner, request.model_dump()])[:32]})
