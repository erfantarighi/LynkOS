# LynkOS

Turn a Raspberry Pi into a managed WiFi router with a modern web UI.

LynkOS wraps NetworkManager, `pppd`, `ip`, and `wireguard-tools` behind a FastAPI backend and a React dashboard. Configure WiFi hotspot, PPPoE upstream, VLANs, static routes, Cloudflare DDNS, WireGuard VPN, DNS adblock, fail2ban, and live speedtests — all from one HTTPS-ready page.

Built on Raspberry Pi OS Bookworm. Should work on any Debian/Ubuntu with NetworkManager.

## Features

- **WiFi Hotspot** — configure SSID, passphrase, band (2.4/5 GHz), channel. Auto-detects NM connections named anything.
- **PPPoE (traditional `pppoeconf` style)** — reads/writes `/etc/ppp/peers/*` and `chap-secrets`. Status derived from `/sys/class/net/ppp*` + `ip addr`.
- **VLANs** — create either raw unmanaged VLANs (via `ip link`, ideal for PPPoE upstream) or NetworkManager-managed ones (with DHCP). Persists across reboots.
- **Static routes** — list, add, delete IPv4/IPv6 routes with idempotent reapply on boot.
- **Dynamic DNS (Cloudflare)** — polls the PPPoE IP, upserts A records (handles apex via `@`), redacts API token in the UI.
- **WireGuard VPN** — one-click setup, add peers with QR codes for mobile, live handshake + byte counters.
- **Speedtest** — supports both Ookla's `speedtest` and Debian's `speedtest-cli`. Auto-detects. Graphs history.
- **DNS adblock** — drops a hosts-style blocklist into the hotspot's dnsmasq. Works for every client on the AP (unless they bypass via Private DNS / iCloud Private Relay).
- **Security** — fail2ban jail for failed logins (external IPs only — all RFC1918 whitelisted) plus in-app rate limit as first line of defence. SSH toggle.
- **Snapshot** — auto-captures your config on every successful change. Re-applies on startup. Download/upload JSON backup for disaster recovery.
- **Live dashboard** — CPU / memory / temp / per-interface throughput graphs with 5-min rolling window, auto-refresh every 2s.
- **Clients list** — sourced from kernel ARP/neighbor table (works without root access to NM lease files).

## Architecture

```
┌──────────────┐     HTTP     ┌───────────────────────┐     sudo helpers     ┌──────────────┐
│  React SPA   │ ───────────▶ │  FastAPI (uvicorn)    │ ──────────────────▶  │  nmcli / ip  │
│  frontend/   │ ◀─────────── │  app/                 │                      │  pppd / wg   │
└──────────────┘              └───────────────────────┘                      │  fail2ban    │
                                        │                                    └──────────────┘
                                        ▼
                                  data/snapshot.json
                                  (0600, service user)
```

Sudo access is mediated by narrow whitelisted helper scripts in `/usr/local/sbin/lynkos-*`, each validating its arguments before invoking the privileged binary.

## Quick start

### On a Raspberry Pi (production)

Prereqs: Raspberry Pi OS Bookworm (Debian 12) with NetworkManager, `pppd`, `pppoe` available. Physical or SSH access.

```bash
git clone https://github.com/erfantarighi/LynkOS.git ~/LynkOS
cd ~/LynkOS
sudo ./install.sh
```

The installer:

1. Installs build tools (Node, Python, uv) + runtime deps (wireguard-tools, fail2ban, qrencode, speedtest-cli).
2. Runs `uv sync` (Python) and `npm run build` (frontend).
3. Prompts for an admin username/password, bcrypt-hashes it, generates a JWT secret.
4. Writes `/etc/default/lynkos`, `/etc/sudoers.d/lynkos`, `/etc/systemd/system/lynkos.service`.
5. Installs helper scripts to `/usr/local/sbin/lynkos-*`.
6. Writes fail2ban filter + jail + systemd-backend default.
7. Enables and starts `lynkos.service`.

Browse to `http://<pi-ip>/` — login screen. The service binds port 80 using `CAP_NET_BIND_SERVICE`, not root.

### On your laptop (development)

```bash
./dev.sh
```

Starts uvicorn with `--reload` on `:8000` and Vite on `:5173` with `LYNKOS_MOCK_MODE=true` so nothing shells out to `nmcli`/`ip`/`pppd`. Default dev login: `admin` / `admin`.

## Configuration

All config via env vars (prefix `LYNKOS_`). See [`.env.example`](.env.example).

| Variable | Purpose |
|---|---|
| `LYNKOS_ADMIN_USERNAME` | Login username |
| `LYNKOS_ADMIN_PASSWORD_HASH` | bcrypt hash of the password (overridden by `data/admin_hash` once changed in the UI) |
| `LYNKOS_JWT_SECRET` | **Must** be a real secret in prod (generate `openssl rand -hex 32`) |
| `LYNKOS_JWT_EXPIRE_MINUTES` | Session lifetime, default 720 |
| `LYNKOS_WAN_INTERFACE` | Default upstream iface (e.g. `eth0`) |
| `LYNKOS_LAN_INTERFACE` | Default hotspot iface (e.g. `wlan0`) |
| `LYNKOS_CORS_ORIGINS` | JSON list of allowed origins |
| `LYNKOS_SNAPSHOT_PATH` | Override snapshot file location |
| `LYNKOS_MOCK_MODE` | Dev-only, bypasses subprocess calls |

### Security notes

- The snapshot (`data/snapshot.json`) and admin hash (`data/admin_hash`) are `0600`, owned by the service user. Back them up carefully — they contain PPPoE password, WireGuard private keys, hotspot passphrase, and your Cloudflare API token.
- fail2ban's `[lynkos]` jail bans external IPs only — RFC1918, loopback, link-local, ULA, and WireGuard subnets are in `ignoreip`. LAN clients can never lock themselves out.
- The in-app rate limiter locks an IP for 10 minutes after 10 failed logins in 5 minutes (HTTP 429). Independent of fail2ban.
- Exposing LynkOS on the public internet: do it behind HTTPS (nginx + Let's Encrypt, Caddy, or Cloudflare Tunnel). The service speaks plain HTTP on :80 by default.

## API

FastAPI auto-generates docs at `/docs` (disable in prod if you don't want them exposed).

Top-level routes:

- `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/change-password`
- `GET/POST /api/wifi/hotspot`, `POST /api/wifi/hotspot/stop`, `GET /api/wifi/scan`
- `GET /api/pppoe/status`, `POST /api/pppoe/{configure,up,down}`, `DELETE /api/pppoe`
- `GET/POST/DELETE /api/vlans`, `DELETE /api/vlans/{name}`
- `GET/POST/DELETE /api/routes`
- `GET/POST /api/ddns`, `POST /api/ddns/update`
- `GET /api/wireguard/status`, `POST /api/wireguard/{setup,peers,teardown}`, `DELETE /api/wireguard/peers/{pubkey}`
- `GET /api/speedtest/history`, `POST /api/speedtest/run`
- `GET /api/fail2ban/status`, `POST /api/fail2ban/unban`, `GET /api/fail2ban/logs`
- `GET/POST /api/adblock`, `POST /api/adblock/{enable,disable,update}`
- `GET /api/ssh`, `POST /api/ssh/{enable,disable}`
- `GET /api/snapshot`, `POST /api/snapshot/{apply,capture}`, `GET /api/snapshot/export`, `POST /api/snapshot/import`, `DELETE /api/snapshot`
- `GET /api/metrics/series`, `GET /api/system/stats`, `GET /api/interfaces`, `GET /api/clients`

## Development

### Project layout

```
app/                    FastAPI backend
  main.py               lifespan + router wiring
  config.py             pydantic-settings
  auth.py, credentials.py, ratelimit.py
  snapshot.py           persistent state + startup reapply
  ddns.py, adblock.py, metrics.py   background tasks
  nm.py                 async subprocess wrapper
  routers/              one file per feature area
  models.py             pydantic DTOs

frontend/               Vite + React + Tailwind + SWR
  src/pages/            one per route
  src/components/       Layout, Sparkline

deploy/                 templates installed to the Pi
  lynkos.service        systemd unit
  lynkos.sudoers        narrow NOPASSWD rules
  lynkos-*              helper scripts (all root-only, arg-validated)
  fail2ban/             filter.d and jail.d configs

tests/                  pytest — pure-logic tests (no shell/network)
install.sh              Pi installer
dev.sh                  local dev runner
```

### Running tests

```bash
uv run pytest           # 41 tests, no network / shell dependencies
uv run ruff check app tests
cd frontend && npx tsc -b --noEmit && npm run build
```

### Adding a new feature

1. New `app/routers/foo.py` → include in `app/main.py`.
2. If privileged: add `deploy/lynkos-foo` helper script, a line to `deploy/lynkos.sudoers`, and an `install` block in `install.sh`.
3. If it should survive reboots: extend `SavedXyz` dataclass in `app/snapshot.py`, call `set_xyz(...)` on success, handle in `apply_all()`.
4. Frontend page at `frontend/src/pages/Foo.tsx`, link from `Layout.tsx`, types in `types.ts`.
5. Tests in `tests/test_foo.py` (pure logic only — don't test subprocess calls).

### Mock mode

Every router checks `is_mock()` (from `LYNKOS_MOCK_MODE=true`) and returns canned data when set. Essential for laptop development and for CI.

## Troubleshooting

**"incomplete config" in DDNS** — Hostnames field is empty. Use `@` for the apex.

**WireGuard peer shows "connected" but can't reach the Pi** — testing from a phone on the same WiFi? That's a NAT-hairpin issue. Switch the phone to mobile data.

**Cloudflare returns edge IPs, not my PPPoE IP** — the A record is proxied (orange cloud). Untick "Proxied" in the DDNS page — Cloudflare only forwards HTTP/HTTPS, not UDP (WireGuard) or other traffic.

**Clients page empty** — make sure the service user can read `ip neigh`. Default install should work; the page falls back gracefully if it can't read dnsmasq lease files (which are root-only).

**fail2ban fails to start** — install `python3-systemd` (`apt install python3-systemd`), then restart. Modern Debian has no `/var/log/auth.log`; fail2ban reads the journal instead.

**PPPoE flaps on reboot** — the VLAN (e.g. `eth0.7`) needs to be unmanaged so NM doesn't fight pppd. Create it as "Unmanaged" from the VLANs page.

**Speedtest: "already installed" apt conflict** — happens if you've already installed Ookla's official `speedtest` binary. `install.sh` skips apt's `speedtest-cli` in that case; LynkOS auto-detects which tool is on `$PATH`.

## Contributing

PRs welcome. Keep the golden rules:

- No new dependencies without a clear reason (this runs on Pi Zero 2W-class hardware).
- New privileged operations go through a validated helper script, never raw sudo with wildcards over user input.
- Stateful features capture themselves into the snapshot so `Re-apply now` and disaster-recovery import keep working.

## License

MIT — see [LICENSE](LICENSE).
