import json

from fastapi.testclient import TestClient

from stylist.config import Settings
from stylist.main import create_app
from stylist.models import Reply, Task


def test_health_does_not_claim_upstream_ready_and_assets_load(tmp_path):
    with TestClient(create_app(Settings(database=str(tmp_path / "state.db")))) as client:
        health = client.get("/health").json()
        assert health["integration_status"] == "unchecked_until_authenticated_probe"
        assert client.get("/mobile/").status_code == 200
        assert client.get("/static/app.js").status_code == 200
        assert client.get("/stylist-api/conversations").status_code == 401
        assert client.post("/stylist-api/integrations/check").status_code == 401


def test_stylist_routes_leave_server_api_namespace_free(tmp_path):
    with TestClient(create_app(Settings(database=str(tmp_path / "routes.db")))) as client:
        paths = client.get("/openapi.json").json()["paths"]
        assert not any(path.startswith("/api/") for path in paths)
        assert "/stylist-api/auth/mobile-login" in paths
        assert "/stylist-api/chat/stream" in paths and "/stylist-api/memories" in paths
        assert client.get("/api/conversations").status_code == 404
        assert client.post("/auth/mobile-login", json={}).status_code == 404
        assert client.post("/stylist-api/auth/mobile-login", json={}).status_code == 422


def test_stream_delivers_structured_result_and_no_internal_details(tmp_path, monkeypatch):
    async def identity(self):
        return "1"
    monkeypatch.setattr("stylist.main.Upstream.identity", identity)
    app = create_app(Settings(database=str(tmp_path / "state.db")))
    async def fake_chat(upstream, request):
        assert upstream.authorization == "Bearer test"
        return Reply(conversation_id="sty_" + "1" * 32, version=1, mode="consult", delivery="advice",
                     message="这三件可以这样穿。", task=Task())
    app.state.engine.chat = fake_chat
    with TestClient(app) as client:
        result = client.post("/stylist-api/chat/stream", headers={"Authorization": "Bearer test"},
                             json={"message": "只咨询穿法", "request_id": "stream-test-001"})
        assert result.status_code == 200 and "event: result" in result.text
        block = result.text.split("event: result\ndata: ")[1].split("\n\n")[0]
        assert json.loads(block)["delivery"] == "advice"


def test_client_cannot_supply_owner_or_charge_parameters(tmp_path):
    with TestClient(create_app(Settings(database=str(tmp_path / "state.db")))) as client:
        response = client.post("/stylist-api/chat", headers={"Authorization": "Bearer test"}, json={
            "message": "帮我搭配", "request_id": "spoof-test-001", "user_id": "another-user"})
        assert response.status_code == 422
        assert client.post("/stylist-api/images/img_test/confirm", headers={"Authorization": "Bearer test"},
                           json={"confirmed": True, "points_cost": 0}).status_code == 422


def test_location_requires_auth_and_explicit_gcj02_is_not_silently_treated_as_wgs84(tmp_path, monkeypatch):
    async def identity(self):
        return "1"
    monkeypatch.setattr("stylist.main.Upstream.identity", identity)
    with TestClient(create_app(Settings(database=str(tmp_path / "location.db")))) as client:
        body = {"latitude": 39.90, "longitude": 116.40}
        assert client.post("/stylist-api/location/resolve", json=body).status_code == 401
        response = client.post("/stylist-api/location/resolve", headers={"Authorization": "Bearer test"},
                               json={**body, "coordinate_system": "gcj02"})
        assert response.status_code == 422
        assert response.json()["code"] == "coordinate_system_unsupported"


def test_expired_login_is_401_for_history_weather_and_service_check(tmp_path, monkeypatch):
    from stylist.errors import AuthenticationExpired
    async def identity(self):
        raise AuthenticationExpired()
    monkeypatch.setattr("stylist.main.Upstream.identity", identity)
    with TestClient(create_app(Settings(database=str(tmp_path / "expired.db")))) as client:
        headers = {"Authorization": "Bearer revoked-test-token"}
        responses = [client.get('/stylist-api/conversations', headers=headers),
                     client.post('/stylist-api/weather/forecast', headers=headers,
                                 json={"location": {"city_name": "北京市"}}),
                     client.post('/stylist-api/integrations/check', headers=headers)]
        for response in responses:
            assert response.status_code == 401
            assert response.json()["code"] == "authentication_expired"


def test_alert_endpoint_reports_unavailable_feed_instead_of_fake_no_warning(tmp_path, monkeypatch):
    async def identity(self):
        return "1"
    async def resolve(self, upstream, city, province=""):
        return {"city_name": "北京市", "province_name": "北京市"}
    monkeypatch.setattr("stylist.main.Upstream.identity", identity)
    monkeypatch.setattr("stylist.weather.WeatherService.resolve", resolve)
    with TestClient(create_app(Settings(database=str(tmp_path / "alerts.db")))) as client:
        body = {"location": {"city_name": "北京市"}}
        assert client.post('/stylist-api/weather/alerts', json=body).status_code == 401
        response = client.post('/stylist-api/weather/alerts', json=body, headers={"Authorization": "Bearer test"})
        assert response.status_code == 200
        assert response.json()["status"] == "unavailable"
        assert "不代表没有预警" in response.json()["message"]
