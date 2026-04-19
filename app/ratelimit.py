"""In-memory rate limiter for /api/auth/login. First line of defence;
fail2ban provides a second, persistent one that also covers SSH."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque


class LoginRateLimiter:
    def __init__(
        self,
        max_attempts: int = 10,
        window_seconds: int = 300,
        lockout_seconds: int = 600,
    ) -> None:
        self.max = max_attempts
        self.window = window_seconds
        self.lockout = lockout_seconds
        self._fails: dict[str, Deque[float]] = defaultdict(deque)
        self._blocked_until: dict[str, float] = {}

    def remaining_lockout(self, ip: str) -> int:
        now = time.time()
        until = self._blocked_until.get(ip)
        if until is None:
            return 0
        if now >= until:
            del self._blocked_until[ip]
            return 0
        return int(until - now)

    def record_failure(self, ip: str) -> None:
        now = time.time()
        attempts = self._fails[ip]
        attempts.append(now)
        while attempts and now - attempts[0] > self.window:
            attempts.popleft()
        if len(attempts) >= self.max:
            self._blocked_until[ip] = now + self.lockout
            attempts.clear()

    def record_success(self, ip: str) -> None:
        self._fails.pop(ip, None)
        self._blocked_until.pop(ip, None)


login_limiter = LoginRateLimiter()
