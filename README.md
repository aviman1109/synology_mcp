# Synology MCP

MCP server for Synology DSM (DS920+, DSM 7.x) — system, DNS, storage, photos, logs, and containers.

## Tools

### System & Network
| Tool | Description |
|---|---|
| `get_system_info` | DSM version, model, CPU/RAM utilization, uptime |
| `get_network_info` | Network interfaces, gateway, DNS servers |
| `check_dsm_update` | Check for DSM firmware updates |
| `list_packages` | Installed packages (filter: running / stopped / all) |
| `get_package_status` | Status of a specific package (e.g. `DNSServer`) |
| `list_shares` | All shared folders |
| `list_scheduled_tasks` | Task Scheduler jobs and next run times |

### DNS Server (split DNS / local overrides)
| Tool | Description |
|---|---|
| `get_dns_status` | Daemon stats + all configured zones |
| `list_dns_zones` | DNS zones (`chengyi.homes`, `synology.me`) |
| `list_dns_records` | All records in a zone |
| `add_dns_record` | Add A / AAAA / CNAME / TXT record |
| `update_dns_record` | Modify an existing record |
| `delete_dns_record` | Remove a record |
| `restart_dns_service` | Restart DNS Server (brief LAN outage) |

### Storage
| Tool | Description |
|---|---|
| `get_storage_info` | Volumes (GB total/used/free, RAID) + disks (model, temp, health) |

### Synology Photos
| Tool | Description |
|---|---|
| `get_synology_photos_status` | Photo/album counts for personal and shared spaces |
| `list_photo_albums` | List albums — `space`: `personal` (default) or `shared` |
| `list_recent_photos` | Most recent photos with filename, time, resolution |
| `get_photo_thumbnail_url` | Session-bound thumbnail URL (LAN only, opens in browser) |
| `download_photo` | Download original photo to `~/Downloads` on the host |

### Logs / Audit
| Tool | Description |
|---|---|
| `get_login_logs` | Recent DSM login/connection events with IP and result |
| `get_system_event_logs` | System events (filter by `err` / `warn` / `info`) |

### Container Manager
| Tool | Description |
|---|---|
| `list_nas_containers` | Docker containers on the NAS with status and ports |

## Configuration

| Env var | Default | Description |
|---|---|---|
| `SYNOLOGY_URL` | — | DSM base URL, e.g. `http://192.168.68.61:9453` |
| `SYNOLOGY_USERNAME` | — | DSM admin username |
| `SYNOLOGY_PASSWORD` | — | DSM admin password |
| `DOWNLOAD_DIR` | `/downloads` | Container path for photo downloads (mounted from host) |
| `PORT` | `38091` | MCP HTTP port |

## Starting

Secrets are injected at startup via `compose-up.sh` (1Password Connect). Do **not** use `refresh-secrets.sh` (removed).

```bash
docker compose up -d synology-mcp        # start
docker compose logs -f synology-mcp      # tail logs
docker compose up -d --build synology-mcp  # rebuild after code changes
```

## Notes

- `download_photo` saves files to `/home/casper/Downloads/` on the host (mounted as `/downloads` in container)
- Thumbnail URLs include the session ID — valid only while the MCP session is active, LAN access only
- `get_login_logs` / `get_system_event_logs` require the **Log Center** package to be running on the NAS
- `list_nas_containers` requires **Container Manager** to be installed

## License

MIT
