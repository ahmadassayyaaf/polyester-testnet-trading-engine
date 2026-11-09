import pytest
from polyester_bot.retry import RetryableExchangeError, retry_write

@pytest.mark.asyncio
async def test_unknown_outcome_reuses_operation_until_success():
    calls = 0
    async def op():
        nonlocal calls; calls += 1
        if calls == 1: raise RetryableExchangeError('ORDER_CREATE_OUTCOME_UNKNOWN', unknown=True)
        return 'accepted'
    result = await retry_write(op, replayable=True, sleep=lambda _: __import__('asyncio').sleep(0))
    assert result == 'accepted' and calls == 2

@pytest.mark.asyncio
async def test_non_replayable_unknown_is_not_retried():
    async def op(): raise RetryableExchangeError('ORDER_CREATE_OUTCOME_UNKNOWN', unknown=True)
    with pytest.raises(RetryableExchangeError): await retry_write(op, replayable=False, sleep=lambda _: __import__('asyncio').sleep(0))
