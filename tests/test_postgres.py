"""Explicit local PostgreSQL regressions, external services remain mocked."""
import os
from urllib.parse import urlsplit

import psycopg
import pytest
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

from stylist.store import Store


@pytest.fixture(autouse=True)
def postgres_backend(monkeypatch):
    dsn = os.environ.get("STYLIST_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Run scripts/check_postgres_local.py explicitly")
    url = urlsplit(dsn)
    if url.hostname != "127.0.0.1" or not url.path.startswith("/stylist_tmp_"):
        pytest.fail("Only disposable loopback PostgreSQL databases are allowed")
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
    from langgraph.checkpoint.postgres import PostgresSaver

    with PostgresSaver.from_conn_string(dsn) as saver:
        saver.setup()
    original = Store.__init__
    monkeypatch.setattr(Store, "__init__", lambda self, path: original(self, dsn))
