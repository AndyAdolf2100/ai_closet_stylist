import pytest

from stylist.errors import StylistError
from stylist.models import ChatRequest, Reply, Task
from stylist.store import Store


def request(**kw):
    return ChatRequest(message="帮我搭一套", request_id="test-request-001", **kw)


def test_replay_conflict_and_isolation(tmp_path):
    store = Store(str(tmp_path / "state.db"))
    req = request()
    cid, claim, state, _ = store.reserve("1", req)
    with pytest.raises(StylistError, match="request_in_progress"):
        store.reserve("1", req)
    reply = Reply(conversation_id=cid, version=1, mode="consult", delivery="advice", message="文字建议", task=Task())
    store.finish("1", req, claim, state, reply)
    assert store.reserve("1", req)[3] == reply
    with pytest.raises(StylistError, match="idempotency_conflict"):
        store.reserve("1", req.model_copy(update={"message": "不同内容"}))
    with pytest.raises(StylistError, match="conversation_not_found"):
        store.history("2", cid)
    with pytest.raises(StylistError, match="conversation_not_found"):
        store.reserve("2", request(conversation_id=cid, expected_version=1))


def test_stale_head_and_expired_worker_cannot_overwrite(tmp_path):
    store = Store(str(tmp_path / "state.db"))
    req = request()
    cid, claim, state, _ = store.reserve("1", req)
    with store.connection() as conn:
        conn.execute("UPDATE stylist_sessions SET lease_until=0 WHERE id=?", (cid,))
    _, newer_claim, _, _ = store.reserve("1", req)
    reply = Reply(conversation_id=cid, version=1, mode="consult", delivery="advice", message="新的结果", task=Task())
    with pytest.raises(StylistError, match="request_superseded"):
        store.finish("1", req, claim, state, reply)
    store.finish("1", req, newer_claim, state, reply)
    stale = request(conversation_id=cid, expected_version=0).model_copy(update={"request_id": "test-request-002"})
    with pytest.raises(StylistError, match="stale_version"):
        store.reserve("1", stale)
