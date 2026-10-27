"""Credentials are supplied on stdin, held in memory, never saved or printed.

First line: {"mobile":...,"code":...,"device_id":...}
Further lines: {"command":"check"} or {"command":"chat","request":{...}}.
"""
import asyncio
import json
import sys
import termios
from datetime import datetime, timezone
from pathlib import Path

from stylist.auth import LoginRequest, login
from stylist.config import Settings
from stylist.errors import StylistError
from stylist.llm import LanguageModel
from stylist.upstream import Upstream, check_integrations


async def main():
    if sys.stdin.isatty():
        terminal = termios.tcgetattr(sys.stdin)
        terminal[3] &= ~termios.ECHO
        termios.tcsetattr(sys.stdin, termios.TCSANOW, terminal)
    settings = Settings.load()
    credentials = json.loads(await asyncio.to_thread(sys.stdin.readline))
    auth = await login(settings, LoginRequest.model_validate(credentials))
    del credentials
    upstream = Upstream(settings, "Bearer " + auth["access_token"])
    print(json.dumps({"login": "ok"}), flush=True)
    while line := await asyncio.to_thread(sys.stdin.readline):
        command = json.loads(line)
        try:
            if command["command"] == "check":
                results = await check_integrations(upstream)
                try:
                    results.append(await LanguageModel(settings).check())
                except StylistError as exc:
                    results.append({"interface": "LLM /chat/completions", "status": "failed", "code": exc.code})
                report = {"checked_at": datetime.now(timezone.utc).isoformat(), "results": results}
                Path("var").mkdir(exist_ok=True)
                Path("var/integrations-live.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
                print(json.dumps(report, ensure_ascii=False), flush=True)
            elif command["command"] == "chat":
                from stylist.engine import Stylist
                from stylist.models import ChatRequest
                from stylist.store import Store
                result = await Stylist(settings, Store(settings.database), LanguageModel(settings)).chat(
                    upstream, ChatRequest.model_validate(command["request"]))
                print(result.model_dump_json(), flush=True)
            elif command["command"] == "suite":
                from live_suite import run
                print(json.dumps(await run(settings, upstream), ensure_ascii=False), flush=True)
            elif command["command"] == "stop":
                break
        except StylistError as exc:
            print(json.dumps({"error": exc.code, "message": exc.message}, ensure_ascii=False), flush=True)


asyncio.run(main())
