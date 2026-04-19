"""Thin wrapper around `nmcli`. Terse mode (`-t -f`) gives predictable colon-separated output."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.config import get_settings


class NmcliError(RuntimeError):
    def __init__(self, cmd: list[str], returncode: int, stderr: str) -> None:
        super().__init__(f"nmcli failed ({returncode}): {' '.join(cmd)}\n{stderr}")
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr


@dataclass
class NmcliResult:
    stdout: str
    stderr: str
    returncode: int


async def run_cmd(
    *args: str, check: bool = True, input_: str | None = None
) -> NmcliResult:
    """Run an arbitrary command. Same return/error shape as `run`."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.PIPE if input_ else None,
    )
    stdout_b, stderr_b = await proc.communicate(input=input_.encode() if input_ else None)
    result = NmcliResult(stdout_b.decode(), stderr_b.decode(), proc.returncode or 0)
    if check and result.returncode != 0:
        raise NmcliError(list(args), result.returncode, result.stderr)
    return result


async def run(*args: str, check: bool = True, input_: str | None = None) -> NmcliResult:
    return await run_cmd("nmcli", *args, check=check, input_=input_)


def parse_terse(text: str, fields: list[str]) -> list[dict[str, str]]:
    """Parse terse nmcli output. Escaped colons (`\\:`) are un-escaped after splitting."""
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line:
            continue
        parts = _split_terse(line)
        # Pad if nmcli returned fewer fields than expected
        parts += [""] * (len(fields) - len(parts))
        rows.append({f: parts[i] for i, f in enumerate(fields)})
    return rows


def _split_terse(line: str) -> list[str]:
    out: list[str] = []
    buf: list[str] = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            buf.append(line[i + 1])
            i += 2
            continue
        if ch == ":":
            out.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    out.append("".join(buf))
    return out


def is_mock() -> bool:
    return get_settings().mock_mode
