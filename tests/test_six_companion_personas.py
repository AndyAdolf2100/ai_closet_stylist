import asyncio
import json
import re
from pathlib import Path
from typing import get_args

import httpx
import pytest
from fastapi.testclient import TestClient

from stylist.config import Settings
from stylist.llm import LanguageModel
from stylist.main import create_app
from stylist.models import ChatRequest, CompanionProfile, Draft, Plan
from stylist.personas import PersonaId, is_male_persona, persona_instructions, progress_message

PERSONAS = get_args(PersonaId)
ORIGINAL_NAMES = re.compile(r"梦梦|亚丝娜|汉库克|女帝|祁煜|祁钰|黎深|秦彻|出包王女|刀剑神域|海贼王|恋与深空|\b(?:momo|asuna|hancock|rafayel|zayne|sylus)\b", re.I)


def test_six_runtime_skills_are_distinct_complete_and_do_not_contain_original_names():
    root = Path(__file__).parents[1] / "stylist" / "skills"
    skills = list(root.glob("*/SKILL.md"))
    assert len(skills) == len(PERSONAS) == 6
    for skill in [*skills, root / "companion-contract.md"]:
        assert not ORIGINAL_NAMES.search(skill.read_text())
    instructions = [persona_instructions(persona) for persona in PERSONAS]
    assert len(set(instructions)) == 6
    for persona, text in zip(PERSONAS, instructions, strict=True):
        assert persona in text
        assert "费用确认" in text and "用户性别与所选助理形象独立" in text
    assert sum(is_male_persona(persona) for persona in PERSONAS) == 3
    assert len({progress_message(persona, "styling") for persona in PERSONAS}) == 6


@pytest.mark.asyncio
async def test_each_selected_skill_reaches_plan_and_style_without_cross_request_leak():
    observed = []

    def respond(request):
        body = json.loads(request.content)
        payload = json.loads(body["messages"][1]["content"])
        selected = payload["assistant_persona"]
        system = body["messages"][0]["content"]
        assert persona_instructions(selected) in system
        assert not ORIGINAL_NAMES.search(system)
        assert [persona for persona in PERSONAS if persona in system] == [selected]
        assert payload["companion_profile"]["agent_name"] == "知秋"
        observed.append((payload["stage"], selected))
        output = Plan(mode="consult", use_inventory=False, conversation_only=True) if payload["stage"] == "plan" else Draft(message="合成回复")
        return httpx.Response(200, json={"choices": [{"message": {"content": output.model_dump_json()}}]})

    model = LanguageModel(Settings(llm_key="synthetic", llm_model="synthetic", llm_url="https://model.invalid"), transport=httpx.MockTransport(respond))
    await asyncio.gather(*(model.generate(stage, {
        "stage": stage, "assistant_persona": persona,
        "companion_profile": CompanionProfile(agent_name="知秋", assistant_persona=persona).model_dump(),
    }, Plan if stage == "plan" else Draft) for persona in PERSONAS for stage in ("plan", "style")))
    assert len(observed) == 12


@pytest.mark.parametrize("persona", PERSONAS)
def test_all_six_profiles_roundtrip_authenticated_api_without_touching_other_accounts(tmp_path, monkeypatch, persona):
    async def identity(self):
        return self.authorization.removeprefix("Bearer ")
    monkeypatch.setattr("stylist.main.Upstream.identity", identity)
    app = create_app(Settings(database=str(tmp_path / "six.db")))
    profile = CompanionProfile(agent_name="知秋", user_gender="女", assistant_persona=persona,
                               mbti="INTJ", style_preferences=["简约"], reply_detail="简洁重点")
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer synthetic-a"}
        saved = client.put("/stylist-api/companion-profile", headers=headers, json=profile.model_dump())
        assert saved.status_code == 200
        assert saved.json()["profile"] == profile.model_dump()
        assert client.get("/stylist-api/companion-profile", headers=headers).json()["profile"] == profile.model_dump()
        assert client.get("/stylist-api/companion-profile", headers={"Authorization": "Bearer synthetic-b"}).json() == {"profile": None}
        request = ChatRequest(message="只讲配色，不查衣橱和天气", request_id="six-profile", companion_profile=profile)
        assert request.assistant_persona == persona
        snapshot = request.model_dump(mode="json")
        profile.assistant_persona = PERSONAS[(PERSONAS.index(persona) + 1) % len(PERSONAS)]
        assert snapshot["assistant_persona"] == snapshot["companion_profile"]["assistant_persona"] == persona


def test_six_character_art_and_skills_are_packaged_with_the_runtime():
    import tomllib
    root = Path(__file__).parents[1]
    patterns = tomllib.loads((root / "pyproject.toml").read_text())["tool"]["setuptools"]["package-data"]["stylist"]
    assert "skills/*/SKILL.md" in patterns and "skills/*.md" in patterns
    packaged = {path for pattern in patterns for path in (root / "stylist").glob(pattern) if path.is_file()}
    character_art = set((root / "stylist/static/assets/characters/candidates-v2").glob("*.png"))
    assert character_art and character_art <= packaged
    for filename in ("companion-characters.js", "companion-characters.css"):
        assert not ORIGINAL_NAMES.search((root / "stylist" / "static" / filename).read_text())
