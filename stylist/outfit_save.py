"""Explicit saves to the Server outfit library, independent of paid try-on."""
import hashlib
import json
import time

from jsonschema import Draft202012Validator
from pydantic import Field, StrictBool

from .errors import StylistError
from .feedback import owned_look
from .models import Model, ProductRef
from .retrieval import resolve_products


class OutfitSaveRequest(Model):
    version: int = Field(ge=1)
    look_index: int = Field(ge=0, le=6)
    include_system: StrictBool = False


class OutfitSaves:
    def __init__(self, store):
        self.store = store

    def context(self, owner, cid, version, index):
        self.store.require_conversation(owner, cid)
        with self.store.connection() as conn:
            _, look = owned_look(conn, owner, cid, version, index)
        if not look.items:
            raise StylistError('outfit_not_saveable', '文字参考还没有实际单品，暂时不能保存搭配。', 422)
        key = hashlib.sha256(json.dumps([owner, cid, version, index]).encode()).hexdigest()
        return key, look

    def _status(self, row):
        if not row:
            return {'status': 'missing'}
        status = row['status']
        # A worker may have stopped after dispatch. Never reclaim this write blindly.
        if status == 'saving' and row['created_at'] + 300 < time.time():
            status = 'unknown'
        if status == 'saved':
            return {'status': status, 'outfit_id': row['outfit_id'], 'outfit_id_type': 2}
        return {'status': status}

    def get(self, owner, cid, version, index):
        key, _ = self.context(owner, cid, version, index)
        with self.store.connection() as conn:
            row = conn.execute('SELECT * FROM stylist_outfit_saves WHERE id=? AND owner_id=?', (key, owner)).fetchone()
        return self._status(row)

    async def save(self, upstream, cid, request):
        owner = await upstream.identity()
        key, look = self.context(owner, cid, request.version, request.look_index)
        existing = self.get(owner, cid, request.version, request.look_index)
        if existing['status'] != 'missing':
            return existing
        if any(p.source == 'system' for p in look.items) and not request.include_system:
            raise StylistError('outfit_system_confirmation_required', '保存这套搭配会将参考款加入个人衣橱，请先确认。', 409)
        refs = [ProductRef(source=p.source, product_id=p.product_id) for p in look.items]
        if any(not r.product_id.isdecimal() or int(r.product_id) < 1 for r in refs):
            raise StylistError('outfit_not_saveable', '部分单品编号无效，请重新搭配。', 422)
        arguments = {'selection_id': 'sel_' + key, 'items': [
            {'source': r.source, 'product_id': int(r.product_id)} for r in refs]}
        async with upstream.mcp(image=True) as mcp:
            tools = await mcp.discover()
            tool = tools.get('save_recommended_outfit')
            if not tool:
                raise StylistError('tool_missing', '当前服务尚未开放保存搭配。', 503)
            if list(Draft202012Validator(tool.inputSchema).iter_errors(arguments)):
                raise StylistError('tool_input_invalid', '当前服务暂不支持保存这套搭配。', 422)
            products = await resolve_products(mcp, refs)
            if {p.key for p in products} != {r.key for r in refs}:
                raise StylistError('outfit_changed', '部分单品已不可用，请重新搭配。', 409)
            with self.store.connection() as conn:
                conn.execute('BEGIN IMMEDIATE')
                row = conn.execute('SELECT * FROM stylist_outfit_saves WHERE id=? AND owner_id=?', (key, owner)).fetchone()
                if row:
                    return self._status(row)
                conn.execute('INSERT INTO stylist_outfit_saves(id,owner_id,conversation_id,status,outfit_id,created_at) VALUES(?,?,?,?,?,?)',
                             (key, owner, cid, 'saving', None, time.time()))
            try:
                result = await mcp.commit_outfit(arguments)
                outfit_id = result.get('outfit_id')
                if isinstance(outfit_id, bool) or not isinstance(outfit_id, int) or outfit_id < 1:
                    raise StylistError('tool_result_invalid', '保存结果不完整。', 502)
                with self.store.connection() as conn:
                    conn.execute("UPDATE stylist_outfit_saves SET status='saved',outfit_id=? WHERE id=? AND owner_id=?",
                                 (outfit_id, key, owner))
            except BaseException as exc:
                with self.store.connection() as conn:
                    conn.execute("UPDATE stylist_outfit_saves SET status='unknown' WHERE id=? AND owner_id=?", (key, owner))
                if not isinstance(exc, Exception):
                    raise
                # A remote error or timeout cannot prove there was no partial write.
                raise StylistError('outfit_save_unknown', '保存结果暂未确认，请到「我的搭配」查看，暂不重复提交。', 502) from None
        return {'status': 'saved', 'outfit_id': outfit_id, 'outfit_id_type': 2}
