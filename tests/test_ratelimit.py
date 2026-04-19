import time

from app.ratelimit import LoginRateLimiter


def test_single_failure_does_not_block():
    rl = LoginRateLimiter(max_attempts=3, window_seconds=60, lockout_seconds=60)
    rl.record_failure("1.2.3.4")
    assert rl.remaining_lockout("1.2.3.4") == 0


def test_blocks_after_max_attempts():
    rl = LoginRateLimiter(max_attempts=3, window_seconds=60, lockout_seconds=60)
    for _ in range(3):
        rl.record_failure("1.2.3.4")
    assert rl.remaining_lockout("1.2.3.4") > 0


def test_block_expires():
    rl = LoginRateLimiter(max_attempts=1, window_seconds=60, lockout_seconds=0)
    rl.record_failure("1.2.3.4")
    # With lockout_seconds=0 the remaining window should immediately be 0
    time.sleep(0.01)
    assert rl.remaining_lockout("1.2.3.4") == 0


def test_success_clears_failures():
    rl = LoginRateLimiter(max_attempts=3, window_seconds=60, lockout_seconds=60)
    rl.record_failure("1.2.3.4")
    rl.record_failure("1.2.3.4")
    rl.record_success("1.2.3.4")
    # Two more attempts shouldn't reach the threshold — counter was reset.
    rl.record_failure("1.2.3.4")
    rl.record_failure("1.2.3.4")
    assert rl.remaining_lockout("1.2.3.4") == 0


def test_per_ip_isolation():
    rl = LoginRateLimiter(max_attempts=2, window_seconds=60, lockout_seconds=60)
    for _ in range(2):
        rl.record_failure("1.2.3.4")
    assert rl.remaining_lockout("1.2.3.4") > 0
    # Different IP should not be affected.
    assert rl.remaining_lockout("5.6.7.8") == 0


def test_old_failures_prune():
    rl = LoginRateLimiter(max_attempts=3, window_seconds=0, lockout_seconds=60)
    # Any failure ages out immediately — attempts deque prunes each time.
    for _ in range(5):
        rl.record_failure("1.2.3.4")
        time.sleep(0.01)
    # Current pattern: window=0 means every new attempt prunes all previous.
    # Should never reach the block threshold.
    assert rl.remaining_lockout("1.2.3.4") == 0
