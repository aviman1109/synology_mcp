"""Configuration for the Synology MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _parse_csv_env(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class AppConfig:
    nas_url: str
    username: str
    password: str
    transport: str
    host: str
    port: int
    path: str
    allowed_hosts: list[str]
    allowed_origins: list[str]
    download_dir: str


def load_app_config() -> AppConfig:
    nas_url = os.getenv("SYNOLOGY_URL", "").rstrip("/")
    if not nas_url:
        raise ValueError("SYNOLOGY_URL must be set (e.g. http://192.168.68.61:5000)")

    username = os.getenv("SYNOLOGY_USERNAME", "")
    if not username:
        raise ValueError("SYNOLOGY_USERNAME must be set")

    password = os.getenv("SYNOLOGY_PASSWORD", "")
    if not password:
        raise ValueError("SYNOLOGY_PASSWORD must be set")

    default_allowed_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    default_allowed_origins = [
        "http://127.0.0.1:*",
        "http://localhost:*",
        "http://[::1]:*",
    ]

    return AppConfig(
        nas_url=nas_url,
        username=username,
        password=password,
        transport=os.getenv("MCP_TRANSPORT", "http"),
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "38091")),
        path=os.getenv("MCP_PATH", "/mcp"),
        allowed_hosts=default_allowed_hosts + _parse_csv_env(os.getenv("MCP_ALLOWED_HOSTS")),
        allowed_origins=default_allowed_origins + _parse_csv_env(os.getenv("MCP_ALLOWED_ORIGINS")),
        download_dir=os.getenv("DOWNLOAD_DIR", "/downloads"),
    )
