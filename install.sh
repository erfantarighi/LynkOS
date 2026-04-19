#!/usr/bin/env bash
# LynkOS installer for Raspberry Pi OS / Debian.
# Installs system deps, builds the app, configures sudoers + systemd, and starts it.
#
# Usage:  sudo ./install.sh
#
set -euo pipefail

# --- config --------------------------------------------------------------
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_USER="${SUDO_USER:-$USER}"
ENV_FILE="/etc/default/lynkos"
SYSTEMD_UNIT="/etc/systemd/system/lynkos.service"
SUDOERS_FILE="/etc/sudoers.d/lynkos"

log()  { printf "\033[1;36m>>\033[0m %s\n" "$*"; }
fail() { printf "\033[1;31m!!\033[0m %s\n" "$*" >&2; exit 1; }

[ "$(id -u)" = 0 ] || fail "run with sudo"
[ -n "$SERVICE_USER" ] && [ "$SERVICE_USER" != "root" ] || \
    fail "don't run as root directly — use 'sudo ./install.sh' from your user"

# --- 0. sanity: repo layout ---------------------------------------------
for f in \
    "$INSTALL_DIR/deploy/lynkos.service" \
    "$INSTALL_DIR/deploy/lynkos.sudoers" \
    "$INSTALL_DIR/deploy/lynkos-pppoe-setup" \
    "$INSTALL_DIR/deploy/lynkos-pppoe-remove" \
    "$INSTALL_DIR/deploy/lynkos-vlan-setup" \
    "$INSTALL_DIR/deploy/lynkos-vlan-remove" \
    "$INSTALL_DIR/deploy/lynkos-wg" \
    "$INSTALL_DIR/deploy/lynkos-fail2ban" \
    "$INSTALL_DIR/deploy/lynkos-adblock"; do
    [ -f "$f" ] || fail "missing $f — re-sync the repo to this machine"
done

# --- 1. verify router toolchain, install app-build deps only -------------
# PPP/PPPoE + NetworkManager are assumed to be already installed on the Pi.
# We only check they're present; if missing, bail so the user can install
# whichever flavor they prefer instead of having us pick one.
for bin in nmcli pppd pppoe; do
    command -v "$bin" >/dev/null || fail "$bin not found — install the router toolchain first"
done

log "apt update && installing build-time deps only"
apt-get update
apt-get install -y --no-install-recommends \
    nodejs npm \
    python3 python3-venv python3-pip \
    wireguard-tools qrencode iptables \
    fail2ban python3-systemd \
    curl ca-certificates openssl

# Speedtest: install Debian's `speedtest-cli` only if no compatible binary is
# already present. Skips on hosts where Ookla's official `speedtest` is
# installed (they own the same path and apt would error out).
if command -v speedtest >/dev/null 2>&1 || command -v speedtest-cli >/dev/null 2>&1; then
    log "speedtest binary already present — skipping apt install"
else
    log "installing speedtest-cli (Debian package)"
    apt-get install -y --no-install-recommends speedtest-cli
fi

# --- 2. uv (Python package/env manager) ----------------------------------
if ! sudo -u "$SERVICE_USER" bash -c 'command -v uv' >/dev/null 2>&1; then
    log "installing uv for $SERVICE_USER"
    sudo -u "$SERVICE_USER" bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
fi
UV_BIN="$(sudo -u "$SERVICE_USER" bash -lc 'command -v uv')"
[ -n "$UV_BIN" ] || fail "uv install failed"

# --- 3. python deps ------------------------------------------------------
log "uv sync (Python deps)"
chown -R "$SERVICE_USER":"$SERVICE_USER" "$INSTALL_DIR"
sudo -u "$SERVICE_USER" bash -lc "cd '$INSTALL_DIR' && '$UV_BIN' sync"

# --- 4. frontend build ---------------------------------------------------
log "npm install + build"
sudo -u "$SERVICE_USER" bash -lc "cd '$INSTALL_DIR/frontend' && npm install && npm run build"

# --- 5. admin password + JWT secret -> /etc/default/lynkos --------------
if [ ! -f "$ENV_FILE" ]; then
    log "generating $ENV_FILE"
    read -r -p "Admin username [admin]: " ADMIN_USER
    ADMIN_USER="${ADMIN_USER:-admin}"
    read -r -s -p "Admin password: " ADMIN_PASS; echo
    [ -n "$ADMIN_PASS" ] || fail "password cannot be empty"

    HASH="$(sudo -u "$SERVICE_USER" bash -lc \
        "cd '$INSTALL_DIR' && '$UV_BIN' run python -c \"import sys, bcrypt; print(bcrypt.hashpw(sys.argv[1].encode(), bcrypt.gensalt()).decode())\" '$ADMIN_PASS'")"
    JWT_SECRET="$(openssl rand -hex 32)"

    cat > "$ENV_FILE" <<EOF
# LynkOS runtime configuration. Reload with: systemctl daemon-reload && systemctl restart lynkos
LYNKOS_ADMIN_USERNAME=$ADMIN_USER
LYNKOS_ADMIN_PASSWORD_HASH=$HASH
LYNKOS_JWT_SECRET=$JWT_SECRET
LYNKOS_WAN_INTERFACE=eth0
LYNKOS_LAN_INTERFACE=wlan0
LYNKOS_CORS_ORIGINS=["*"]
EOF
    chmod 0640 "$ENV_FILE"
else
    log "$ENV_FILE already exists — leaving untouched"
fi

# --- 6a. pppoe helper scripts --------------------------------------------
log "installing helper scripts to /usr/local/sbin"
install -m 0750 -o root -g root \
    "$INSTALL_DIR/deploy/lynkos-pppoe-setup"  /usr/local/sbin/lynkos-pppoe-setup
install -m 0750 -o root -g root \
    "$INSTALL_DIR/deploy/lynkos-pppoe-remove" /usr/local/sbin/lynkos-pppoe-remove
install -m 0750 -o root -g root \
    "$INSTALL_DIR/deploy/lynkos-vlan-setup"   /usr/local/sbin/lynkos-vlan-setup
install -m 0750 -o root -g root \
    "$INSTALL_DIR/deploy/lynkos-vlan-remove"  /usr/local/sbin/lynkos-vlan-remove
install -m 0750 -o root -g root \
    "$INSTALL_DIR/deploy/lynkos-wg"           /usr/local/sbin/lynkos-wg
install -m 0750 -o root -g root \
    "$INSTALL_DIR/deploy/lynkos-fail2ban"     /usr/local/sbin/lynkos-fail2ban
install -m 0750 -o root -g root \
    "$INSTALL_DIR/deploy/lynkos-adblock"      /usr/local/sbin/lynkos-adblock

# Adblock data directory (owned by service user so it can write the hosts file)
log "preparing /var/lib/lynkos/adblock"
/usr/local/sbin/lynkos-adblock prepare "$SERVICE_USER"

# --- 6c. fail2ban filter + jail (external IPs only) ----------------------
if [ -d /etc/fail2ban ]; then
    log "installing fail2ban filter and jail"
    install -m 0644 "$INSTALL_DIR/deploy/fail2ban/filter.d/lynkos.conf" \
        /etc/fail2ban/filter.d/lynkos.conf
    install -m 0644 "$INSTALL_DIR/deploy/fail2ban/jail.d/lynkos.conf" \
        /etc/fail2ban/jail.d/lynkos.conf
    # Force systemd backend globally — Raspberry Pi OS has no /var/log/auth.log
    install -m 0644 "$INSTALL_DIR/deploy/fail2ban/jail.d/00-systemd.conf" \
        /etc/fail2ban/jail.d/00-systemd.conf
    systemctl enable fail2ban 2>/dev/null || true
    systemctl restart fail2ban 2>/dev/null || true
fi

# --- 6b. sudoers for nmcli + pon/poff + helpers --------------------------
log "installing $SUDOERS_FILE"
sed "s|__USER__|$SERVICE_USER|g" "$INSTALL_DIR/deploy/lynkos.sudoers" > "$SUDOERS_FILE.tmp"
visudo -cf "$SUDOERS_FILE.tmp" >/dev/null || { rm -f "$SUDOERS_FILE.tmp"; fail "sudoers syntax error"; }
install -m 0440 -o root -g root "$SUDOERS_FILE.tmp" "$SUDOERS_FILE"
rm -f "$SUDOERS_FILE.tmp"

# --- 7. systemd unit -----------------------------------------------------
log "installing $SYSTEMD_UNIT"
sed -e "s|__USER__|$SERVICE_USER|g" -e "s|__INSTALL_DIR__|$INSTALL_DIR|g" \
    "$INSTALL_DIR/deploy/lynkos.service" > "$SYSTEMD_UNIT"

# Remove legacy drop-ins from earlier iterations — the main unit file now
# owns port 80, CAP_NET_BIND_SERVICE, and SupplementaryGroups directly.
if [ -d /etc/systemd/system/lynkos.service.d ]; then
    rm -f /etc/systemd/system/lynkos.service.d/port.conf \
          /etc/systemd/system/lynkos.service.d/groups.conf
    rmdir /etc/systemd/system/lynkos.service.d 2>/dev/null || true
fi

# --- 8. ensure NetworkManager is enabled (no-op if already running) -----
if systemctl list-unit-files | grep -q '^NetworkManager\.service'; then
    systemctl enable --now NetworkManager || true
fi

# --- 9. enable + start lynkos --------------------------------------------
log "starting lynkos"
systemctl daemon-reload
systemctl enable lynkos
systemctl restart lynkos    # restart so config changes (e.g. port) actually apply

sleep 1
if systemctl --no-pager --quiet is-active lynkos; then
    IP=$(hostname -I | awk '{print $1}')
    PORT=$(ss -ltnp 2>/dev/null | awk '/uvicorn/ {split($4,a,":"); print a[length(a)]; exit}')
    log "lynkos is running → http://${IP}:${PORT:-80}"
else
    systemctl --no-pager status lynkos
    fail "service did not start"
fi
