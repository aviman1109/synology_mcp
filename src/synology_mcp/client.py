"""Synology DSM REST API client.

DSM Web API reference: https://global.download.synology.com/download/Document/Software/DeveloperGuide/Os/DSM/All/enu/DSM_Login_Web_API_Guide_enu.pdf

Auth flow:
  1. POST /webapi/entry.cgi  api=SYNO.API.Auth method=login  → sid (session ID)
  2. Subsequent calls include _sid=<sid> in params
  3. On cleanup: api=SYNO.API.Auth method=logout
"""

from __future__ import annotations

import hashlib
from typing import Any

import httpx

_TIMEOUT = httpx.Timeout(20.0)
_WEBAPI = "/webapi/entry.cgi"


class SynologyClient:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self._base_url = base_url
        self._username = username
        self._password = password
        self._sid: str | None = None
        self._http = httpx.AsyncClient(
            base_url=base_url,
            timeout=_TIMEOUT,
            verify=False,  # self-signed certs common on home NAS
        )

    # ── Auth ──────────────────────────────────────────────────────────────

    async def login(self) -> None:
        """Obtain a session ID from DSM."""
        r = await self._http.get(
            _WEBAPI,
            params={
                "api": "SYNO.API.Auth",
                "version": "6",
                "method": "login",
                "account": self._username,
                "passwd": self._password,
                "session": "synology_mcp",
                "format": "sid",
            },
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("success"):
            code = data.get("error", {}).get("code", "?")
            raise RuntimeError(f"DSM login failed (error code {code})")
        self._sid = data["data"]["sid"]

    async def logout(self) -> None:
        if not self._sid:
            return
        await self._http.get(
            _WEBAPI,
            params={
                "api": "SYNO.API.Auth",
                "version": "6",
                "method": "logout",
                "session": "synology_mcp",
                "_sid": self._sid,
            },
        )
        self._sid = None

    async def _get(self, params: dict) -> Any:
        """Execute a DSM API call, auto-login if needed."""
        if not self._sid:
            await self.login()
        params["_sid"] = self._sid
        r = await self._http.get(_WEBAPI, params=params)
        r.raise_for_status()
        data = r.json()
        # Auto re-login on session expiry (error 119)
        if not data.get("success") and data.get("error", {}).get("code") == 119:
            self._sid = None
            await self.login()
            params["_sid"] = self._sid
            r = await self._http.get(_WEBAPI, params=params)
            r.raise_for_status()
            data = r.json()
        if not data.get("success"):
            code = data.get("error", {}).get("code", "?")
            raise RuntimeError(f"DSM API error (code {code}) for {params.get('api')}.{params.get('method')}")
        return data.get("data")

    async def _post(self, data: dict) -> Any:
        """Execute a DSM API POST call."""
        if not self._sid:
            await self.login()
        data["_sid"] = self._sid
        r = await self._http.post(_WEBAPI, data=data)
        r.raise_for_status()
        resp = r.json()
        if not resp.get("success"):
            code = resp.get("error", {}).get("code", "?")
            raise RuntimeError(f"DSM API error (code {code}) for {data.get('api')}.{data.get('method')}")
        return resp.get("data")

    # ── System ────────────────────────────────────────────────────────────

    async def get_system_info(self) -> dict[str, Any]:
        """Get DSM version, model, hostname, uptime, CPU, RAM."""
        info = await self._get({
            "api": "SYNO.Core.System",
            "version": "3",
            "method": "info",
        })
        resource = await self._get({
            "api": "SYNO.Core.System.Utilization",
            "version": "1",
            "method": "get",
        })
        return {"system": info, "utilization": resource}

    # ── Packages ──────────────────────────────────────────────────────────

    async def list_packages(self, filter_status: str | None = None) -> list[dict[str, Any]]:
        """List installed packages. filter_status: 'running', 'stop', or None for all."""
        params: dict = {
            "api": "SYNO.Package",
            "version": "1",
            "method": "list",
            "additional": '["status"]',
        }
        data = await self._get(params)
        packages = data.get("packages", []) if data else []
        if filter_status:
            packages = [p for p in packages if p.get("status") == filter_status]
        return packages

    async def get_package_status(self, package_id: str) -> dict[str, Any]:
        """Get status of a specific package (e.g. 'DNSServer')."""
        data = await self._get({
            "api": "SYNO.Package",
            "version": "1",
            "method": "get",
            "id": package_id,
            "additional": '["status"]',
        })
        return data or {}

    # ── DNS Server ────────────────────────────────────────────────────────

    async def list_dns_zones(self) -> list[dict[str, Any]]:
        """List all DNS zones configured in Synology DNS Server."""
        data = await self._get({
            "api": "SYNO.DNSServer.Zone",
            "version": "1",
            "method": "list",
        })
        return data.get("items", []) if data else []

    async def list_dns_records(self, zone: str) -> list[dict[str, Any]]:
        """List all DNS records in a zone."""
        data = await self._get({
            "api": "SYNO.DNSServer.Zone.Record",
            "version": "1",
            "method": "list",
            "zone_name": zone,
            "domain_name": zone,
        })
        return data.get("items", []) if data else []

    async def add_dns_record(
        self,
        zone: str,
        hostname: str,
        type: str,
        data: str,
        ttl: int = 86400,
    ) -> dict[str, Any]:
        """Add a DNS record to a zone.
        type: A, AAAA, CNAME, MX, TXT, etc.
        data: IP address for A records, hostname for CNAME, etc.
        """
        result = await self._post({
            "api": "SYNO.DNSServer.Zone.Record",
            "version": "1",
            "method": "create",
            "zone_name": zone,
            "domain_name": zone,
            "subdomain": hostname,
            "rr_type": type,
            "rr_info": data,
            "rr_ttl": str(ttl),
        })
        return result or {"success": True}

    async def update_dns_record(
        self,
        zone: str,
        hostname: str,
        type: str,
        data: str,
        old_data: str,
        ttl: int = 86400,
    ) -> dict[str, Any]:
        """Update an existing DNS record."""
        result = await self._post({
            "api": "SYNO.DNSServer.Zone.Record",
            "version": "1",
            "method": "set",
            "zone_name": zone,
            "domain_name": zone,
            "subdomain": hostname,
            "rr_type": type,
            "rr_info": data,
            "old_rr_info": old_data,
            "rr_ttl": str(ttl),
        })
        return result or {"success": True}

    async def delete_dns_record(
        self,
        zone: str,
        hostname: str,
        type: str,
        data: str,
    ) -> dict[str, Any]:
        """Delete a DNS record from a zone."""
        result = await self._post({
            "api": "SYNO.DNSServer.Zone.Record",
            "version": "1",
            "method": "delete",
            "zone_name": zone,
            "domain_name": zone,
            "subdomain": hostname,
            "rr_type": type,
            "rr_info": data,
        })
        return result or {"success": True}

    async def restart_dns_service(self) -> dict[str, Any]:
        """Restart the DNS Server package."""
        result = await self._post({
            "api": "SYNO.Package.Control",
            "version": "1",
            "method": "restart",
            "id": "DNSServer",
        })
        return result or {"success": True}

    # ── Network ───────────────────────────────────────────────────────────

    async def get_network_info(self) -> dict[str, Any]:
        """Get NAS network configuration: interfaces, gateway, DNS."""
        data = await self._get({
            "api": "SYNO.Core.Network",
            "version": "1",
            "method": "get",
        })
        return data or {}

    # ── Shares ────────────────────────────────────────────────────────────

    async def list_shares(self) -> list[dict[str, Any]]:
        """List all shared folders."""
        data = await self._get({
            "api": "SYNO.FileStation.List",
            "version": "2",
            "method": "list_share",
        })
        return data.get("shares", []) if data else []

    # ── Update check ──────────────────────────────────────────────────────

    async def check_dsm_update(self) -> dict[str, Any]:
        """Check if a DSM update is available."""
        data = await self._get({
            "api": "SYNO.Core.Upgrade.Server",
            "version": "1",
            "method": "check",
        })
        return data or {}

    # ── DNS daemon ────────────────────────────────────────────────────────

    async def get_dns_daemon_status(self) -> dict[str, Any]:
        """Get DNS Server daemon statistics."""
        data = await self._get({
            "api": "SYNO.DNSServer.DaemonStatus",
            "version": "1",
            "method": "get",
        })
        return data or {}

    # ── Task Scheduler ────────────────────────────────────────────────────

    async def list_scheduled_tasks(self) -> list[dict[str, Any]]:
        """List all scheduled tasks."""
        data = await self._get({
            "api": "SYNO.Core.TaskScheduler",
            "version": "2",
            "method": "list",
        })
        return data.get("tasks", []) if data else []

    # ── Storage ───────────────────────────────────────────────────────────

    async def get_storage_info(self) -> dict[str, Any]:
        """Get summarised volume and disk status."""
        raw = await self._get({
            "api": "SYNO.Storage.CGI.Storage",
            "version": "1",
            "method": "load_info",
        })
        if not raw:
            return {}

        def _bytes_to_gb(b) -> float | None:
            try:
                return round(int(b) / 1024 ** 3, 1)
            except (TypeError, ValueError):
                return None

        volumes = []
        for v in raw.get("volumes", []):
            size = v.get("size", {})
            total_gb = _bytes_to_gb(size.get("total"))
            used_gb = _bytes_to_gb(size.get("used"))
            free_gb = round(total_gb - used_gb, 1) if total_gb and used_gb else None
            pct_used = round(used_gb / total_gb * 100, 1) if total_gb and used_gb else None
            volumes.append({
                "id": v.get("id"),
                "display_name": v.get("vol_desc") or v.get("id"),
                "status": v.get("status"),
                "fs_type": v.get("fs_type"),
                "raid_type": v.get("raidType"),
                "total_gb": total_gb,
                "used_gb": used_gb,
                "free_gb": free_gb,
                "used_pct": pct_used,
            })

        disks = []
        for d in raw.get("disks", []):
            disks.append({
                "id": d.get("id"),
                "model": d.get("model"),
                "size_gb": _bytes_to_gb(d.get("size_total")),
                "temp_c": d.get("temp"),
                "status": d.get("status"),
                "health": d.get("health", d.get("status")),
            })

        return {"volumes": volumes, "disks": disks}

    # ── Synology Photos ───────────────────────────────────────────────────────

    async def get_photos_status(self) -> dict[str, Any]:
        """Get Synology Photos photo/album counts for personal and shared spaces."""
        result: dict[str, Any] = {}
        for key, api in [
            ("personal_photos", "SYNO.Foto.Browse.Item"),
            ("personal_albums", "SYNO.Foto.Browse.NormalAlbum"),
            ("shared_photos", "SYNO.FotoTeam.Browse.Item"),
            ("shared_albums", "SYNO.FotoTeam.Browse.NormalAlbum"),
        ]:
            try:
                data = await self._get({"api": api, "version": "1", "method": "count"})
                result[key] = data.get("count") if data else None
            except Exception as e:
                result[key] = f"unavailable ({e})"
        return result

    async def list_photo_albums(self, space: str = "personal") -> list[dict[str, Any]]:
        """List Synology Photos albums. space: 'personal' (default) or 'shared'."""
        api = "SYNO.FotoTeam.Browse.NormalAlbum" if space == "shared" else "SYNO.Foto.Browse.NormalAlbum"
        data = await self._get({
            "api": api,
            "version": "1",
            "method": "list",
            "offset": 0,
            "limit": 200,
            "sort_by": "album_name",
            "sort_direction": "asc",
        })
        return data.get("list", []) if data else []

    async def list_recent_photos(self, limit: int = 20) -> list[dict[str, Any]]:
        """List most recently taken photos (sorted by capture time desc)."""
        data = await self._get({
            "api": "SYNO.Foto.Browse.Item",
            "version": "1",
            "method": "list",
            "offset": 0,
            "limit": limit,
            "sort_by": "takentime",
            "sort_direction": "desc",
            "additional": '["thumbnail","resolution","video_convert","video_meta"]',
        })
        items = data.get("list", []) if data else []
        return [
            {
                "id": p.get("id"),
                "filename": p.get("filename"),
                "type": p.get("type"),  # "photo" or "video"
                "takentime": p.get("time"),
                "resolution": p.get("additional", {}).get("resolution"),
            }
            for p in items
        ]

    async def get_photo_thumbnail_url(self, photo_id: int, size: str = "sm") -> dict[str, Any]:
        """Return a session-bound thumbnail URL for a photo.
        size: sm (240px) | m (320px) | xl (1280px)
        Note: URL valid for current session only; requires LAN access.
        """
        if not self._sid:
            await self.login()
        url = (
            f"{self._base_url}{_WEBAPI}"
            f"?api=SYNO.Foto.Thumbnail&version=1&method=get"
            f"&id={photo_id}&type={size}&unit_id={photo_id}&_sid={self._sid}"
        )
        return {"photo_id": photo_id, "size": size, "url": url, "note": "LAN-only, session expires on logout"}

    async def download_photo(self, photo_id: int, dest_path: str) -> dict[str, Any]:
        """Download an original photo from Synology Photos to dest_path."""
        import os
        if not self._sid:
            await self.login()
        r = await self._http.get(
            _WEBAPI,
            params={
                "api": "SYNO.Foto.Download",
                "version": "1",
                "method": "download",
                "unit_id": f"[{photo_id}]",
                "_sid": self._sid,
            },
        )
        r.raise_for_status()
        os.makedirs(os.path.dirname(dest_path) if os.path.dirname(dest_path) else ".", exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(r.content)
        return {
            "photo_id": photo_id,
            "saved_to": dest_path,
            "size_bytes": len(r.content),
            "content_type": r.headers.get("content-type", "unknown"),
        }

    # ── Logs / Audit ──────────────────────────────────────────────────────────

    async def get_current_logins(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get currently active connection sessions from DSM."""
        data = await self._get({
            "api": "SYNO.Core.CurrentConnection",
            "version": "1",
            "method": "list",
        })
        items = data.get("items", []) if data else []
        return [
            {
                "user": item.get("who"),
                "from": item.get("from"),
                "protocol": item.get("type"),
                "time": item.get("time"),
                "description": item.get("descr"),
            }
            for item in items[:limit]
        ]

    async def get_login_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get historical login/connection log entries from DSM Log Center."""
        data = await self._get({
            "api": "SYNO.Core.SyslogClient.Log",
            "version": "1",
            "method": "list",
            "logtype": "connection",
            "offset": 0,
            "limit": limit,
        })
        return data.get("items", []) if data else []

    async def get_system_event_logs(self, limit: int = 50, level: str = "") -> list[dict[str, Any]]:
        """Get DSM system event logs.
        level: '' for all | 'err' for errors | 'warn' for warnings | 'info' for info
        """
        params: dict[str, Any] = {
            "api": "SYNO.Core.SyslogClient.Log",
            "version": "1",
            "method": "list",
            "logtype": "syslog",
            "offset": 0,
            "limit": limit,
        }
        if level:
            params["level"] = level
        data = await self._get(params)
        return data.get("items", []) if data else []

    # ── Container Manager (Docker) ────────────────────────────────────────────

    async def list_nas_containers(self) -> list[dict[str, Any]]:
        """List Docker containers managed by Synology Container Manager."""
        data = await self._get({
            "api": "SYNO.Docker.Container",
            "version": "1",
            "method": "list",
            "limit": -1,
            "offset": 0,
        })
        containers = data.get("containers", []) if data else []
        return [
            {
                "name": c.get("name"),
                "status": c.get("status"),
                "image": c.get("image"),
                "running": c.get("status") == "running",
                "ports": c.get("port_bindings"),
            }
            for c in containers
        ]

    async def aclose(self) -> None:
        try:
            await self.logout()
        finally:
            await self._http.aclose()
