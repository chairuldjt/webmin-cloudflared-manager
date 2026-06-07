# Cloudflared Manager

A [Webmin](https://webmin.com) module to manage multiple Cloudflared tunnels — start/stop/restart services, view per-tunnel logs, edit YAML configs, create and delete tunnels.

## Features

- **Multi-Tunnel Management** — List, start, stop, restart, and delete individual tunnels
- **Service Control** — Start/Stop/Restart the main Cloudflared daemon
- **Status Monitoring** — Real-time service status for each tunnel and the main daemon
- **Log Viewer** — View per-tunnel or global logs via `journalctl` with filtering and auto-refresh
- **Config Editor** — Edit per-tunnel YAML configuration files directly from Webmin
- **Auto-Detection** — Automatically detects cloudflared binary and config file paths
- **Manual Override** — Set custom paths for binary and config files
- **Tunnel Creation** — Create new tunnels via cloudflared CLI with auto-setup of systemd service and config
- **Systemd Integration** — Manages both main `cloudflared.service` and per-tunnel `cloudflared-tunnel-<name>.service`

## Installation

Download the latest `.wbm.gz` from [Releases](https://github.com/chairuladitya/webmin-cloudflared-manager/releases) and install via **Webmin → Webmin Modules → Install Module**.

Or manually extract:

```bash
tar -xzf cloudflared-manager.wbm.gz -C /opt/webmin/
```

The module appears under **System → Cloudflared Manager**.

## Requirements

- Webmin 2.x
- Cloudflared installed and configured
- systemd

## Files

```
cloudflared/
├── module.info    # Module metadata
├── index.cgi      # Dashboard — tunnel list, service controls, status
├── logs.cgi       # Per-tunnel log viewer with filtering & auto-refresh
├── config.cgi     # Settings, tunnel creation, per-tunnel config editor
└── config         # Module configuration (binary path, config path)
```

## Usage

### Dashboard (`index.cgi`)
- View overall cloudflared version and main service status
- See all configured tunnels with their current status
- Start, stop, restart individual tunnels or the main service
- Quick links to config and logs for each tunnel

### Settings & Config (`config.cgi`)
- Set cloudflared binary path (auto-detected or manual)
- Set default config file path
- Create new tunnels with automatic systemd service setup
- Edit per-tunnel YAML configuration files
- Delete tunnels with cleanup

### Log Viewer (`logs.cgi`)
- Select which service/tunnel to view logs from
- Adjust number of lines shown
- Filter logs by keyword (grep)
- Enable auto-refresh (30s interval)

## Development

```bash
git clone https://github.com/chairuladitya/webmin-cloudflared-manager.git
cd webmin-cloudflared-manager
```

Edit the CGI files and test by copying to your Webmin modules directory.

## License

MIT
