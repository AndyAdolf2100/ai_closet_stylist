"""Owned, reversible outfit votes and bounded soft style evidence."""
from typing import Literal

from pydantic import Field

from .errors import StylistError
from .models import Model, Reply
from .personas import PersonaId, outfit_feedback_receipt


class OutfitFeedback(Model):
    version: int = Field(ge=1)
    look_index: int = Field(ge=0, le=6)
    vote: Literal['like', 'dislike'] | None = None
    assistant_persona: PersonaId | None = None


def owned_look(conn, owner, cid, version, index, *, allow_saved_snapshot=False):
    row = conn.execute('SELECT reply_json FROM stylist_messages WHERE owner_id=? AND conversation_id=? AND version=?',
                       (owner, cid, version)).fetchone()
    if not row:
        raise StylistError('feedback_not_found', '找不到当前账号的这套搭配。', 404)
    reply = Reply.model_validate_json(row['reply_json'])
    saved_snapshot = (allow_saved_snapshot and reply.delivery == 'advice'
                      and reply.product_entry is None and reply.subject_product is None)
    if index >= len(reply.looks) or reply.pending_confirmation or (reply.delivery != 'outfit' and not saved_snapshot):
        raise StylistError('feedback_not_available', '这条记录还没有完成的搭配。', 422)
    return reply, reply.looks[index]


def read_feedback(store, owner, cid, version, index):
    with store.connection() as conn:
        owned_look(conn, owner, cid, version, index)
        row = conn.execute('SELECT vote FROM stylist_outfit_feedback WHERE owner_id=? AND conversation_id=? AND version=? AND look_index=?',
                           (owner, cid, version, index)).fetchone()
    return {'vote': row['vote'] if row else None}


def save_feedback(store, owner, cid, request):
    with store.connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        reply, look = owned_look(conn, owner, cid, request.version, request.look_index)
        args = (owner, cid, request.version, request.look_index)
        # Repeated writes replace the same evidence; withdrawal removes its influence.
        conn.execute('DELETE FROM stylist_outfit_feedback WHERE owner_id=? AND conversation_id=? AND version=? AND look_index=?', args)
        if request.vote:
            conn.execute('INSERT INTO stylist_outfit_feedback(owner_id,conversation_id,version,look_index,vote,style_name,gender,personal) VALUES(?,?,?,?,?,?,?,?)',
                         (*args, request.vote, look.style_name, reply.task.gender or '', int(not bool(reply.task.target_description))))
    can_reference = bool(look.style_name.strip() and not reply.task.target_description and store.memory_book(owner).enabled)
    return {'vote': request.vote, 'message': outfit_feedback_receipt(request.assistant_persona, request.vote, can_reference)}


def style_evidence(store, owner, task):
    """Only positive, explicit style labels; never turn ratings into hard exclusions."""
    if task.target_description or not store.memory_book(owner).enabled:
        return []
    with store.connection() as conn:
        rows = conn.execute('SELECT conversation_id,version,style_name FROM stylist_outfit_feedback WHERE owner_id=? AND vote=? AND personal=1 AND gender=? ORDER BY updated_at DESC,conversation_id,version DESC LIMIT 100',
                            (owner, 'like', task.gender or '')).fetchall()
    styles = {}
    for row in rows:
        style = row['style_name'].strip()
        if style:
            styles.setdefault(style, set()).add((row['conversation_id'], row['version']))
    return [{'style_name': style, 'positive_versions': min(len(versions), 3),
             'weight': round(min(len(versions), 3) * .1, 1)}
            for style, versions in sorted(styles.items(), key=lambda item: (-len(item[1]), item[0]))[:5]]
