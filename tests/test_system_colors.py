import hashlib
import json

import pytest
from pydantic import ValidationError

from stylist.models import ChatRequest, CompanionProfile, Reply, Task
from stylist.store import Store


def test_color_profiles_survive_reopening_and_remain_account_scoped(tmp_path):
    path = str(tmp_path / "colors.db")
    store = Store(path)
    a = CompanionProfile(assistant_persona="male_confident_v1", color_scheme="system", user_gender="女")
    store.save_companion_profile("color-a", a)
    store.save_companion_profile("color-b", CompanionProfile())
    reopened = Store(path)
    assert reopened.companion_profile("color-a") == a
    assert reopened.companion_profile("color-b").color_scheme == "companion"
    assert reopened.companion_profile("unknown") is None


def test_legacy_profiles_default_and_unknown_color_values_are_rejected():
    assert CompanionProfile.model_validate_json('{"assistant_persona":"male_calm_v1"}').color_scheme == "companion"
    with pytest.raises(ValidationError):
        CompanionProfile(color_scheme="dark")


def test_colors_are_excluded_from_dialogue_context():
    a = CompanionProfile(assistant_persona="male_artistic_v1", color_scheme="system")
    b = a.model_copy(update={"color_scheme": "companion"})
    assert a.dialogue_data() == b.dialogue_data()
    assert "color_scheme" not in a.dialogue_data()
    assert a.model_dump()["color_scheme"] == "system"


def test_changing_only_colors_does_not_invalidate_an_existing_request_receipt(tmp_path):
    store = Store(str(tmp_path / "requests.db"))
    request = ChatRequest(message="只聊聊穿法，不查衣橱", request_id="same-color-request", companion_profile=CompanionProfile())
    cid, claim, state, _ = store.reserve("color-a", request)
    legacy = json.loads(request.model_dump_json(exclude={"upload_action_id", "regenerate_outfit", "regenerate_from_version", "new_clothes", "chat_image"}))
    legacy["companion_profile"].pop("color_scheme")
    legacy_digest = hashlib.sha256(json.dumps(legacy, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    with store.connection() as conn:
        stored_digest = conn.execute("SELECT digest FROM stylist_requests WHERE request_id=?", (request.request_id,)).fetchone()["digest"]
    assert stored_digest == legacy_digest
    reply = Reply(conversation_id=cid, version=1, mode="consult", delivery="advice", message="衣角自然放下。", task=Task())
    store.finish("color-a", request, claim, state, reply)
    changed = request.model_copy(update={"companion_profile": request.companion_profile.model_copy(update={"color_scheme": "system"})})
    assert store.reserve("color-a", changed)[3] == reply
