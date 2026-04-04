"""MCP tool definitions for the Synology MCP server."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from synology_mcp.client import SynologyClient


def _j(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def register_tools(app: FastMCP, client: SynologyClient, download_dir: str = "/downloads") -> None:

    # ── System ────────────────────────────────────────────────────────────

    @app.tool()
    async def get_system_info() -> str:
        """
        Get Synology NAS system information: DSM version, model, serial number,
        CPU utilization (1/5/15-min load), memory usage, network throughput,
        disk I/O, and uptime.
        """
        return _j(await client.get_system_info())

    @app.tool()
    async def get_network_info() -> str:
        """
        Get NAS network configuration: all interfaces with IP/mask, gateway,
        DNS servers, and link status.
        """
        return _j(await client.get_network_info())

    @app.tool()
    async def check_dsm_update() -> str:
        """
        Check whether a DSM firmware update is available for this NAS.
        Returns available=true/false and version info if an update exists.
        """
        return _j(await client.check_dsm_update())

    # ── Packages ──────────────────────────────────────────────────────────

    @app.tool()
    async def list_packages(filter_status: str = "") -> str:
        """
        List installed packages on the Synology NAS.
        filter_status: 'running' for running only, 'stop' for stopped only,
                       leave empty to show all.
        Common package IDs: DNSServer, ContainerManager, SurveillanceStation,
        ActiveInsight, MailPlus-Server, LogCenter, ProxyServer, SMBService.
        """
        return _j(await client.list_packages(filter_status or None))

    @app.tool()
    async def get_package_status(package_id: str) -> str:
        """
        Get status of a specific Synology package.
        package_id: e.g. 'DNSServer', 'ContainerManager', 'SurveillanceStation'
        """
        return _j(await client.get_package_status(package_id))

    # ── Shares / FileStation ──────────────────────────────────────────────

    @app.tool()
    async def list_shares() -> str:
        """
        List all shared folders on the NAS (e.g. photo, docker, shared, homes).
        """
        return _j(await client.list_shares())

    # ── Scheduled tasks ───────────────────────────────────────────────────

    @app.tool()
    async def list_scheduled_tasks() -> str:
        """
        List all tasks in the Synology Task Scheduler (enabled/disabled,
        next run time, last result).
        """
        return _j(await client.list_scheduled_tasks())

    # ── DNS Server ────────────────────────────────────────────────────────

    @app.tool()
    async def get_dns_status() -> str:
        """
        Get Synology DNS Server daemon status and statistics:
        recursive clients, TCP clients, memory alert flag.
        Also lists all configured DNS zones and their enabled state.
        """
        daemon = await client.get_dns_daemon_status()
        zones = await client.list_dns_zones()
        return _j({"daemon": daemon, "zones": zones})

    @app.tool()
    async def list_dns_zones() -> str:
        """
        List all DNS zones configured in Synology DNS Server.
        Requires the DNS Server package to be installed and running.
        """
        return _j(await client.list_dns_zones())

    @app.tool()
    async def list_dns_records(zone: str) -> str:
        """
        List all DNS records in a specific DNS zone.
        zone: the zone name (e.g. 'chengyi.homes')
        """
        return _j(await client.list_dns_records(zone))

    @app.tool()
    async def add_dns_record(
        zone: str,
        hostname: str,
        type: str,
        data: str,
        ttl: int = 86400,
    ) -> str:
        """
        Add a DNS record to a zone (for split DNS / local overrides).
        zone: DNS zone name (e.g. 'chengyi.homes')
        hostname: subdomain only (e.g. 'nas' → creates nas.chengyi.homes)
        type: A | AAAA | CNAME | MX | TXT
        data: IP for A records, FQDN for CNAME
        ttl: seconds (default 86400)

        Example: nas.chengyi.homes → 192.168.68.61 (LAN split DNS)
          zone='chengyi.homes', hostname='nas', type='A', data='192.168.68.61'
        """
        return _j(await client.add_dns_record(zone, hostname, type, data, ttl))

    @app.tool()
    async def update_dns_record(
        zone: str,
        hostname: str,
        type: str,
        data: str,
        old_data: str,
        ttl: int = 86400,
    ) -> str:
        """
        Update an existing DNS record.
        zone: DNS zone name
        hostname: subdomain name
        type: record type (A, CNAME, etc.)
        data: new record value
        old_data: current record value (identifies which record to update)
        ttl: new TTL in seconds
        """
        return _j(await client.update_dns_record(zone, hostname, type, data, old_data, ttl))

    @app.tool()
    async def delete_dns_record(
        zone: str,
        hostname: str,
        type: str,
        data: str,
    ) -> str:
        """
        Delete a DNS record from a zone.
        zone: DNS zone name
        hostname: subdomain name
        type: record type (A, CNAME, etc.)
        data: record value (identifies exact record)
        """
        return _j(await client.delete_dns_record(zone, hostname, type, data))

    @app.tool()
    async def restart_dns_service() -> str:
        """
        Restart the Synology DNS Server package.
        Use after DNS record changes if they don't propagate automatically.
        WARNING: briefly interrupts local DNS resolution on the LAN.
        """
        return _j(await client.restart_dns_service())

    # ── Storage ───────────────────────────────────────────────────────────

    @app.tool()
    async def get_storage_info() -> str:
        """
        Get NAS storage summary: volumes (total/used/free GB, RAID type,
        filesystem, health) and disks (model, size, temperature, health status).
        """
        return _j(await client.get_storage_info())

    # ── Synology Photos ───────────────────────────────────────────────────────

    @app.tool()
    async def get_synology_photos_status() -> str:
        """
        Get Synology Photos overview: total photo and album counts
        for both personal space and shared (team) space.
        """
        return _j(await client.get_photos_status())

    @app.tool()
    async def list_photo_albums(space: str = "personal") -> str:
        """
        List Synology Photos albums.
        space: 'personal' (default) — your own albums
               'shared'   — shared/team space albums
        Returns album name, item count, and cover photo info.
        """
        return _j(await client.list_photo_albums(space))

    @app.tool()
    async def list_recent_photos(limit: int = 20) -> str:
        """
        List the most recently taken photos from Synology Photos personal space.
        limit: number of photos to return (default 20, max 200)
        Returns filename, type (photo/video), capture time, and resolution.
        """
        return _j(await client.list_recent_photos(limit))

    @app.tool()
    async def get_photo_thumbnail_url(photo_id: int, size: str = "sm") -> str:
        """
        Get a session-bound thumbnail URL for a specific photo.
        photo_id: the numeric photo ID (from list_recent_photos)
        size: 'sm' (240px) | 'm' (320px) | 'xl' (1280px)
        Note: URL is valid for the current session and requires LAN access.
        Open the returned URL in a browser on the local network to view.
        """
        return _j(await client.get_photo_thumbnail_url(photo_id, size))

    @app.tool()
    async def download_photo(photo_id: int, filename: str = "") -> str:
        """
        Download an original photo from Synology Photos to the local workspace.
        photo_id: numeric photo ID (from list_recent_photos)
        filename: output filename (optional). Defaults to 'photo_<id>.jpg'.
                  File is saved to the configured download directory on the host.
        Returns the saved path, file size, and content type.
        """
        import os
        dest = os.path.join(download_dir, filename or f"photo_{photo_id}.jpg")
        return _j(await client.download_photo(photo_id, dest))

    # ── Logs / Audit ──────────────────────────────────────────────────────────

    @app.tool()
    async def get_current_logins(limit: int = 50) -> str:
        """
        Get currently active connection sessions on Synology DSM.
        Shows who is connected right now, from which IP, protocol (SSH/SMB/DSM/etc.), and since when.
        limit: max entries to return (default 50)
        """
        return _j(await client.get_current_logins(limit))

    @app.tool()
    async def get_login_history(limit: int = 50) -> str:
        """
        Get historical login/connection log entries from Synology DSM Log Center.
        Shows who signed in/out, from which IP, when, and whether it succeeded.
        Requires Log Center package.
        limit: number of log entries to return (default 50)
        """
        return _j(await client.get_login_history(limit))

    @app.tool()
    async def get_system_event_logs(limit: int = 50, level: str = "") -> str:
        """
        Get DSM system event logs.
        limit: number of entries (default 50)
        level: '' for all | 'err' for errors only | 'warn' for warnings | 'info' for info
        Covers package installs, service restarts, storage events, etc.
        """
        return _j(await client.get_system_event_logs(limit, level))

    # ── Container Manager ─────────────────────────────────────────────────────

    @app.tool()
    async def list_nas_containers() -> str:
        """
        List Docker containers managed by Synology Container Manager.
        Returns container name, image, running status, and port bindings.
        Requires the Container Manager package to be installed on the NAS.
        """
        return _j(await client.list_nas_containers())
