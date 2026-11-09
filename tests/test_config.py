import pytest
from polyester_bot.config import Settings


def base(**kwargs):
    values = dict(api_key_id=None, api_private_key=None, subaccount_id=None, symbol="BTC-USDT", qty=__import__('decimal').Decimal('0.1'), half_spread_bps=__import__('decimal').Decimal('20'), max_inventory=__import__('decimal').Decimal('1'), max_open_orders=2, db_path='x.db', log_level='INFO', dms_timeout_seconds=30, dms_refresh_seconds=10, enable_live_trading=False)
    values.update(kwargs)
    return Settings(**values)

def test_defaults_fail_closed():
    assert base().enable_live_trading is False

def test_live_requires_credentials():
    with pytest.raises(ValueError, match="requires API key"):
        base(enable_live_trading=True).validate()

def test_dead_man_bounds():
    with pytest.raises(ValueError):
        base(dms_timeout_seconds=9).validate()
