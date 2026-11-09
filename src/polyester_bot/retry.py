from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable

RETRYABLE_CODES = {"RATE_LIMIT_EXCEEDED", "SYSTEM_RATE_LIMITED", "OVERLOADED", "RATE_LIMIT_AUTHORITY_UNAVAILABLE"}


class RetryableExchangeError(Exception):
    def __init__(self, code: str, retry_after: float | None = None, unknown: bool = False):
        super().__init__(code)
        self.code, self.retry_after, self.unknown = code, retry_after, unknown


async def retry_write(
    operation: Callable[[], Awaitable[object]], *, replayable: bool, attempts: int = 5,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> object:
    for attempt in range(attempts):
        try:
            return await operation()
        except RetryableExchangeError as exc:
            retryable = exc.code in RETRYABLE_CODES or (replayable and exc.unknown)
            if not retryable or attempt == attempts - 1:
                raise
            delay = exc.retry_after if exc.retry_after is not None else min(8.0, 0.5 * 2**attempt)
            await sleep(delay + random.uniform(0, 0.25))
    raise AssertionError("unreachable")
