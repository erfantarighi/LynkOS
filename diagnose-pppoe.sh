#!/usr/bin/env bash
# Run on the Raspberry Pi as the service user:
#   cd ~/temp/LynkOS && bash diagnose-pppoe.sh > diag.txt 2>&1
# Then send diag.txt back.

set +e

section() { echo; echo "=== $* ==="; }

section "uname / os-release"
uname -a
cat /etc/os-release 2>/dev/null | head -5

section "ppp interfaces in /sys/class/net"
ls -la /sys/class/net/ | grep -i ppp
echo "--- operstate ---"
for i in /sys/class/net/ppp*; do
    [ -e "$i" ] || continue
    echo "$i/operstate = $(cat "$i/operstate" 2>/dev/null)"
    echo "$i/carrier   = $(cat "$i/carrier"   2>/dev/null)"
done

section "ip -br link (ppp)"
ip -br link show type ppp 2>&1

section "ip -4 addr (all)"
ip -br -4 addr 2>&1

section "ip -4 addr show ppp0 / ppp1"
ip -o -4 addr show ppp0 2>&1
ip -o -4 addr show ppp1 2>&1

section "pppd + pppoe processes"
ps -ef | grep -E '[p]ppd|[p]ppoe'

section "peer files"
ls -la /etc/ppp/peers/ 2>&1

section "peer file contents (safe — no secrets)"
for f in /etc/ppp/peers/*; do
    [ -f "$f" ] || continue
    echo "--- $f ---"
    grep -vE '^\s*(#|$)' "$f" | grep -vE 'password'
done

section "default route"
ip -4 route | head -20

section "backend health"
curl -sk http://localhost:8000/api/health

section "python view — what /api/pppoe/status sees"
if command -v uv >/dev/null; then
    uv run python <<'PY' 2>&1
from pathlib import Path
import re, subprocess
net = Path("/sys/class/net")
ppp = sorted(p.name for p in net.glob("ppp*"))
print("ppp interfaces:", ppp)
if ppp:
    out = subprocess.run(["ip","-o","-4","addr","show",ppp[0]], capture_output=True, text=True)
    print("ip addr rc:", out.returncode)
    print("stdout:", repr(out.stdout))
    print("stderr:", repr(out.stderr))
    m = re.search(r"inet\s+(\S+)", out.stdout)
    print("parsed IP:", m.group(1).split("/")[0] if m else None)
for name in ("lynkos-wan","dsl-provider","provider"):
    p = Path(f"/etc/ppp/peers/{name}")
    print(f"{name}: exists={p.exists()}")
PY
else
    echo "uv not on PATH — skipping python view"
fi

section "systemd status (lynkos)"
systemctl --no-pager status lynkos 2>&1 | head -20

section "journal (last 30 lines of lynkos)"
sudo -n journalctl -u lynkos -n 30 --no-pager 2>&1
