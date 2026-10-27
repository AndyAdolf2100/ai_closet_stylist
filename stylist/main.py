import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .auth import LoginRequest, login
from .config import Settings
from .engine import Stylist
from .errors import AuthenticationExpired, StylistError
from .export import export_wardrobe
from .images import ImageConfirmRequest, ImageQuoteRequest, ImageService
from .llm import LanguageModel
from .models import ChatRequest, ForecastRequest, LocateRequest
from .progress import events as progress_events
from .store import Store
from .upstream import Upstream, check_integrations


def require_token(authorization):
    if not authorization or not authorization.startswith("Bearer ") or not authorization[7:].strip():
        raise AuthenticationExpired()
    return authorization


def create_app(settings=None):
    settings = settings or Settings.load()
    app = FastAPI(title="AI Closet Stylist", version="0.1.0")
    app.state.settings = settings
    store = Store(settings.database)
    model = LanguageModel(settings)
    engine = Stylist(settings, store, model)
    images = ImageService(store)
    alerts = engine.alerts
    app.state.engine = engine
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                       allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])

    @app.exception_handler(StylistError)
    async def error_handler(request, exc):
        return JSONResponse({"code": exc.code, "message": exc.message}, status_code=exc.status)

    @app.get("/health")
    async def health():
        return {"status": "live", "llm_configured": bool(settings.llm_key and settings.llm_model),
                "integration_status": "unchecked_until_authenticated_probe"}

    @app.post("/api/integrations/check")
    async def integrations(authorization: str | None = Header(default=None)):
        upstream = Upstream(settings, require_token(authorization))
        # Invalid login must prompt reauthentication, not a successful report of widespread outages.
        await upstream.identity()
        results = await check_integrations(upstream)
        try:
            results.append(await model.check())
        except StylistError as exc:
            results.append({"interface": "LLM /chat/completions", "status": "failed", "code": exc.code})
        report = {"checked_at": datetime.now(timezone.utc).isoformat(),
                  "server_url": settings.server_url, "results": results}
        Path("var").mkdir(exist_ok=True)
        Path("var/integrations.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
        return report

    @app.post("/auth/mobile-login")
    async def mobile_login(request: LoginRequest):
        return await login(settings, request)

    @app.post("/api/location/resolve")
    async def resolve_location(request: LocateRequest, authorization: str | None = Header(default=None)):
        upstream = Upstream(settings, require_token(authorization))
        await upstream.identity()
        if request.coordinate_system != "wgs84":
            raise StylistError("coordinate_system_unsupported", "当前定位接口使用浏览器WGS84坐标；高德GCJ-02或百度BD-09坐标不能直接混用，请选择浏览器定位或手动选城市。", 422)
        return await engine.weather.locate(upstream, request.latitude, request.longitude)

    @app.post("/api/weather/forecast")
    async def weather_forecast(request: ForecastRequest, authorization: str | None = Header(default=None)):
        upstream = Upstream(settings, require_token(authorization))
        await upstream.identity()
        return await engine.weather.forecast(upstream, request.location.city_name,
            request.location.province_name, request.scope, request.event_date)

    @app.post("/api/weather/alerts")
    async def weather_alerts(request: ForecastRequest, authorization: str | None = Header(default=None)):
        upstream = Upstream(settings, require_token(authorization))
        await upstream.identity()
        city = await engine.weather.resolve(upstream, request.location.city_name, request.location.province_name)
        return await alerts.lookup(city)

    @app.post("/api/chat", response_model=None)
    async def chat(request: ChatRequest, authorization: str | None = Header(default=None)):
        return await engine.chat(Upstream(settings, require_token(authorization)), request)

    @app.post("/api/chat/stream")
    async def stream_chat(request: ChatRequest, authorization: str | None = Header(default=None)):
        token = require_token(authorization)

        def event(name, payload):
            return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

        async def events():
            queue = asyncio.Queue()
            context_token = progress_events.set(queue)
            task = asyncio.create_task(engine.chat(Upstream(settings, token), request))
            progress_events.reset(context_token)
            try:
                yield event("progress", {"stage": "connecting", "message": "衣衣收到啦，正在连接你的衣橱。"})
                while not task.done():
                    update = asyncio.create_task(queue.get())
                    try:
                        done, _ = await asyncio.wait({task, update}, timeout=10, return_when=asyncio.FIRST_COMPLETED)
                        if update in done:
                            yield event("progress", update.result())
                        elif not done:
                            yield ": keepalive\n\n"
                    finally:
                        if not update.done():
                            update.cancel()
                            try:
                                await update
                            except asyncio.CancelledError:
                                pass
                result = await task
                yield event("result", result.model_dump(mode="json"))
            except StylistError as exc:
                yield event("error", {"code": exc.code, "message": exc.message})
            except Exception as exc:
                logging.getLogger(__name__).error("chat_failed type=%s", type(exc).__name__)
                yield event("error", {"code": "internal_error", "message": "这次处理未完成，原需求已保留，请稍后重试。"})
            finally:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/conversations")
    async def conversations(authorization: str | None = Header(default=None)):
        owner = await Upstream(settings, require_token(authorization)).identity()
        return await asyncio.to_thread(store.conversations, owner)

    @app.post("/api/wardrobe/export")
    async def wardrobe_export(authorization: str | None = Header(default=None)):
        return await export_wardrobe(Upstream(settings, require_token(authorization)))

    @app.get("/api/conversations/{conversation_id}")
    async def history(conversation_id: str, authorization: str | None = Header(default=None)):
        owner = await Upstream(settings, require_token(authorization)).identity()
        return await asyncio.to_thread(store.history, owner, conversation_id)

    @app.post("/api/images/quote")
    async def image_quote(request: ImageQuoteRequest, authorization: str | None = Header(default=None)):
        return await images.quote(Upstream(settings, require_token(authorization)), request)

    @app.post("/api/images/{action_id}/confirm")
    async def image_confirm(action_id: str, request: ImageConfirmRequest,
                            authorization: str | None = Header(default=None)):
        return await images.confirm(Upstream(settings, require_token(authorization)), action_id, request.confirmed)

    @app.get("/api/images/{action_id}")
    async def image_status(action_id: str, authorization: str | None = Header(default=None)):
        owner = await Upstream(settings, require_token(authorization)).identity()
        return images.status(owner, action_id)

    @app.get("/")
    @app.get("/mobile/")
    async def index():
        return FileResponse(Path(__file__).with_name("static") / "index.html")

    app.mount("/static", StaticFiles(directory=Path(__file__).with_name("static")), name="static")

    return app


app = create_app()
