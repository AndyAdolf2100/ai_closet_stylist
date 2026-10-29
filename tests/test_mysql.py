"""Same behavioral checks against real MySQL, explicitly opted in by the local runner."""
import asyncio
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import pytest
from langgraph.checkpoint.base import empty_checkpoint

# Reuse behavior assertions, now backed by a temporary MySQL database instead of SQLite.
from test_companion_identity import (  # noqa: F401
    test_companion_profiles_are_account_scoped_and_survive_reopening,
    test_optional_personal_preferences_validate_and_survive_account_scoped_storage,
    test_profile_api_requires_identity_and_rejects_owner_spoofing,
)
from test_durable_graph import (  # noqa: F401
    Model,
    Upstream,
    test_approval_status_api_and_draining,
    test_confirmation_is_owner_scoped_and_new_user_cannot_resume,
    test_confirmation_survives_restart_and_cancel_never_generates,
    test_stale_confirmation_cannot_override_newer_conversation,
    test_transient_model_failure_retries_only_style_node,
)
from test_images import (  # noqa: F401
    test_changed_price_requires_new_confirmation,
    test_concurrent_confirmation_dispatches_once,
    test_quote_and_cancel_do_not_dispatch_or_charge,
    test_uncertain_dispatch_is_not_automatically_retried,
)
from test_memory import (  # noqa: F401
    test_explicit_remember_is_atomic_idempotent_and_does_not_call_model,
    test_full_memory_save_rolls_back_chat_and_preserves_notes,
    test_memory_api_identity_validation_and_conflict,
    test_memory_cross_conversation_pause_and_no_implicit_collection,
    test_memory_persistence_conflict_pause_delete_and_account_isolation,
    test_memory_snapshot_survives_retry_but_deletion_affects_next_request,
    test_natural_explicit_memory_is_saved_with_success_receipt,
    test_remember_that_uses_previous_user_fact_not_invented_assistant_fact,
    test_unambiguous_natural_command_saves_even_if_model_would_omit_action,
    test_unresolved_save_never_returns_a_false_success,
)
from test_store import (  # noqa: F401
    test_conversation_title_uses_first_saved_question_and_stays_owner_scoped,
    test_replay_conflict_and_isolation,
    test_stale_head_and_expired_worker_cannot_overwrite,
)

from stylist.config import Settings
from stylist.engine import Stylist
from stylist.errors import StylistError
from stylist.models import ChatRequest, CompanionProfile
from stylist.mysql_checkpoint import AsyncMySQLSaver
from stylist.store import Store


class PrivateDSN(str):
    def __repr__(self):
        return "<local disposable MySQL database>"


@pytest.fixture(autouse=True)
def mysql_backend(monkeypatch):
    dsn = os.environ.get("STYLIST_TEST_MYSQL_DSN")
    if not dsn:
        pytest.skip("显式运行 scripts/check_mysql_local.py 才执行真实 MySQL 回归")
    url = urlsplit(dsn)
    if url.hostname not in {"127.0.0.1", "localhost", "::1"} or not url.path.startswith("/stylist_tmp_"):
        pytest.fail("MySQL 回归仅允许本机一次性测试库")
    store = Store(dsn)
    with store.connection() as conn:
        for table in ("stylist_checkpoint_writes", "stylist_checkpoints", "stylist_image_actions",
                      "stylist_messages", "stylist_requests", "stylist_sessions", "stylist_companion_profiles", "stylist_memory_books"):
            conn.execute(f"DELETE FROM {table}")
    original = Store.__init__
    monkeypatch.setattr(Store, "__init__", lambda self, path: original(self, dsn))
    return PrivateDSN(dsn)


def test_profile_upsert_unicode_and_case_sensitive_owner(mysql_backend):
    store = Store(mysql_backend)
    profile = CompanionProfile(agent_name="衣衣")
    store.save_companion_profile("Owner", profile)
    changed = profile.model_copy(update={"agent_name": "小衣👗"})
    store.save_companion_profile("Owner", changed)
    assert Store(mysql_backend).companion_profile("Owner") == changed
    assert store.companion_profile("owner") is None


@pytest.mark.asyncio
async def test_restart_resumes_failed_node_without_repeating_understanding(mysql_backend):
    model = Model()
    model.fail_style = True
    request = ChatRequest(message="只咨询穿法", request_id="mysql-restart-001")
    with pytest.raises(StylistError, match="model_output_invalid"):
        await Stylist(Settings(), Store(mysql_backend), model).chat(Upstream(), request)
    model.fail_style = False
    restarted = Stylist(Settings(), Store(mysql_backend), model)
    reply = await restarted.chat(Upstream(), request)
    assert reply.delivery == "advice"
    assert model.calls == ["plan", "style", "style"]
    assert await restarted.chat(Upstream(), request) == reply
    assert model.calls == ["plan", "style", "style"]
    with restarted.store.connection() as conn:
        rows = conn.execute("SELECT checkpoint FROM stylist_checkpoints").fetchall()
        writes = conn.execute("SELECT value FROM stylist_checkpoint_writes").fetchall()
    assert rows and writes
    assert all(b"test-secret-not-in-checkpoint" not in r["checkpoint"] for r in rows)
    assert all(b"test-secret-not-in-checkpoint" not in r["value"] for r in writes)


def test_transaction_rolls_back(mysql_backend):
    store = Store(mysql_backend)
    with pytest.raises(RuntimeError):
        with store.connection() as conn:
            conn.execute("INSERT INTO stylist_companion_profiles(owner_id,profile_json) VALUES(?,?)", ("rollback", "{}"))
            raise RuntimeError("abort")
    assert store.companion_profile("rollback") is None


def test_concurrent_reservation_has_one_winner(mysql_backend):
    store = Store(mysql_backend)
    request = ChatRequest(message="咨询穿法", request_id="mysql-concurrent-001")

    def reserve():
        try:
            return store.reserve("owner", request)
        except StylistError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: reserve(), range(4)))
    assert sum(isinstance(result, tuple) for result in results) == 1
    assert results.count("request_in_progress") == 3


@pytest.mark.asyncio
async def test_hard_killed_process_resumes_from_mysql(mysql_backend, tmp_path):
    marker = tmp_path / "in-style"
    code = '''
import asyncio,os,sys
from pathlib import Path
from stylist.engine import Stylist
from stylist.config import Settings
from stylist.models import Plan,ChatRequest
from stylist.store import Store
class U:
    async def identity(self): return 'owner-1'
class M:
    async def generate(self,name,payload,result_type):
        if name=='plan': return Plan(mode='consult',use_inventory=False)
        Path(sys.argv[1]).write_text('style_started')
        await asyncio.Event().wait()
asyncio.run(Stylist(Settings(),Store(os.environ['STYLIST_TEST_MYSQL_DSN']),M()).chat(
    U(),ChatRequest(message='只咨询穿法',request_id='mysql-killed-001')))
'''
    child = await asyncio.create_subprocess_exec(sys.executable, "-c", code, str(marker))
    try:
        async with asyncio.timeout(15):
            while not marker.exists():
                await asyncio.sleep(.05)
    finally:
        if child.returncode is None:
            child.kill()
        await child.wait()
    store = Store(mysql_backend)
    with store.connection() as conn:
        conn.execute("UPDATE stylist_sessions SET lease_until=0")
    model = Model()
    reply = await Stylist(Settings(), store, model).chat(Upstream(), ChatRequest(
        message="只咨询穿法", request_id="mysql-killed-001"))
    assert reply.delivery == "advice" and model.calls == ["style"]


@pytest.mark.asyncio
async def test_checkpoint_pending_writes_history_and_delete(mysql_backend):
    config = {"configurable": {"thread_id": "checkpoint-test", "checkpoint_ns": ""}}
    saver = AsyncMySQLSaver(mysql_backend)
    checkpoint = empty_checkpoint()
    config1 = await saver.aput(config, checkpoint, {"source": "input", "step": 0, "parents": {}}, {})
    await saver.aput_writes(config1, [("test", {"中文": "内容👗"})], "task-1")
    await saver.aput_writes(config1, [("test", "不能覆盖原结果")], "task-1")
    restored = await AsyncMySQLSaver(mysql_backend).aget_tuple(config)
    assert restored.pending_writes == [("task-1", "test", {"中文": "内容👗"})]
    child = empty_checkpoint()
    config2 = await saver.aput(config1, child, {"source": "loop", "step": 1, "parents": {}}, {})
    assert (await saver.aget_tuple(config2)).parent_config == config1
    assert len([c async for c in saver.alist(config)]) == 2
    assert len([c async for c in saver.alist(config, filter={"step": 0})]) == 1
    assert len([c async for c in saver.alist(config, limit=1)]) == 1
    assert len([c async for c in saver.alist(config, before=config2)]) == 1
    await saver.adelete_thread("checkpoint-test")
    assert await saver.aget_tuple(config) is None


@pytest.mark.asyncio
async def test_graph_lock_blocks_another_worker_then_releases(mysql_backend):
    first, second = AsyncMySQLSaver(mysql_backend), AsyncMySQLSaver(mysql_backend)
    async with first.lock_thread("same-request"):
        with pytest.raises(StylistError, match="request_in_progress"):
            async with second.lock_thread("same-request"):
                pytest.fail("second worker acquired active request")
    async with second.lock_thread("same-request"):
        await asyncio.sleep(0)
