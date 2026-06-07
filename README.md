# Cloudflared Manager

A [Webmin](https://webmin.com) module to manage Cloudflared tunnel service — start/stop/restart, view logs, and edit configuration.

## Features

- **Service Control** — Start, Stop, and Restart the Cloudflared tunnel service
- **Status Monitoring** — View real-time service status (active/inactive)
- **Log Viewer** — Browse recent logs via `journalctl`
- **Config Editor** — Edit `/etc/cloudflared/config.yml` directly from Webmin

## Installation

1. Download the latest `.wbm.gz` from [Releases](https://github.com/chairuladitya/webmin-cloudflared-manager/releases)
2. In Webmin, go to **Webmin → Webmin Modules → Install Module**
3. Choose the downloaded file and install
4. The module appears under **System → Cloudflared Manager**

Or manually extract to Webmin modules directory:

```bash
tar -xzf cloudflared-manager.wbm.gz -C /opt/webmin/
```

## Requirements

- Webmin (tested on 2.x)
- Cloudflared installed and configured as a systemd service
- Perl modules: `WebminCore`

## Files

```
cloudflared/
├── module.info    # Module metadata
├── index.cgi      # Main dashboard (status + controls)
├── logs.cgi       # Log viewer
├── config.cgi     # Configuration editor
└── config         # Module config (paths)
```

## Development

```bash
git clone https://github.com/chairuladitya/webmin-cloudflared-manager.git
cd webmin-cloudflared-manager
```

Edit the CGI files and test by copying to your Webmin modules directory.

## License

MIT
