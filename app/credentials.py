"""Admin password hash storage.

On first boot the hash comes from `LYNKOS_ADMIN_PASSWORD_HASH` in the
environment (written by install.sh to /etc/default/lynkos). Once the user
changes their password from the UI, we persist the new hash to
`<install_dir>/data/admin_hash` (0600, owned by the service user) so it
survives restarts without needing sudo.
"""
from pathlib import Path

from app.config import get_settings

_DEFAULT_RELPATH = Path("data") / "admin_hash"


def _hash_path() -> Path:
    return Path(__file__).resolve().parent.parent / _DEFAULT_RELPATH


def current_admin_hash() -> str:
    p = _hash_path()
    if p.exists():
        try:
            raw = p.read_text().strip()
            if raw:
                return raw
        except OSError:
            pass
    return get_settings().admin_password_hash


def set_admin_hash(new_hash: str) -> None:
    p = _hash_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(new_hash)
    tmp.chmod(0o600)
    tmp.replace(p)
