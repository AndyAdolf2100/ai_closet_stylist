import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import yaml


@dataclass(frozen=True)
class Settings:
    server_url: str = "http://127.0.0.1:8080"
    mcp_url: str = "http://127.0.0.1:8080/mcp"
    llm_url: str = ""
    llm_model: str = ""
    llm_key: str = field(default="", repr=False)
    database: str = field(default="var/stylist.sqlite3", repr=False)
    checkpoint_database: str = field(default="", repr=False)
    request_timeout: float = 20
    llm_timeout: float = 90
    image_timeout: float = 240
    max_candidates: int = 60
    login_public_key: str = ""
    login_app_version: str = "1.2.0"
    alerts_url: str = ""
    alerts_key: str = field(default="", repr=False)
    cors_origins: tuple[str, ...] = ("http://127.0.0.1:8465", "http://localhost:8465")

    @classmethod
    def load(cls):
        local_path = Path(os.getenv("STYLIST_LOCAL_CONFIG", "config/local.yaml"))
        local = yaml.safe_load(local_path.read_text()) or {} if local_path.is_file() else {}
        # Optional migration convenience: read credentials, never import the old app.
        raw = {}
        path = os.getenv("STYLIST_LEGACY_CONFIG")
        if path:
            raw = yaml.safe_load(Path(path).read_text()) or {}
        llm = dict(raw.get("llm") or {})
        models = llm.get("models") or []
        if isinstance(models, list):
            selected = next((x for x in models if x.get("id") == llm.get("default_model_id")), {})
            llm.update(selected)
        servers = (raw.get("mcp_tool_routing") or {}).get("servers") or []
        upstream = next((x for x in servers if x.get("enabled", True)), {})
        mcp_url = os.getenv("STYLIST_MCP_URL", upstream.get("url") or cls.mcp_url)
        origin = urlsplit(mcp_url)
        server_url = os.getenv("STYLIST_SERVER_URL", f"{origin.scheme}://{origin.netloc}")
        return cls(
            server_url=server_url.rstrip("/"), mcp_url=mcp_url,
            llm_url=os.getenv("STYLIST_LLM_URL", llm.get("base_url") or "").rstrip("/"),
            llm_model=os.getenv("STYLIST_LLM_MODEL", llm.get("model") or ""),
            llm_key=os.getenv("STYLIST_LLM_KEY", llm.get("api_key") or ""),
            database=os.getenv("STYLIST_DATABASE", local.get("database") or cls.database),
            checkpoint_database=os.getenv("STYLIST_CHECKPOINT_DATABASE", local.get("checkpoint_database") or ""),
            login_public_key=os.getenv("STYLIST_LOGIN_PUBLIC_KEY", (raw.get("upstream_auth") or {}).get("public_key_path") or ""),
            login_app_version=os.getenv("STYLIST_LOGIN_APP_VERSION", (raw.get("upstream_auth") or {}).get("app_version") or "1.2.0"),
            alerts_url=os.getenv("STYLIST_ALERTS_URL", ""),
            alerts_key=os.getenv("STYLIST_ALERTS_KEY", ""),
        )
