from decimal import Decimal
import pytest
from polyester_bot.rules import PairRules

RAW = dict(symbol='BTC-USDT', symbolId=1, status='ENABLED', tickSize='0.01', stepSize='0.001', minQtyBase='0.01', minNotionalQuote='5', maxOrderNotionalQuote='100000')

def rules(): return PairRules.from_raw(RAW)

def test_valid_order(): rules().validate_order(Decimal('100.01'), Decimal('0.05'))
@pytest.mark.parametrize(('price','qty','code'), [(Decimal('100.001'), Decimal('0.05'),'PRICE_TICK_SIZE'), (Decimal('100'),Decimal('0.0005'),'QTY_STEP_SIZE'), (Decimal('100'),Decimal('0.01'),'MIN_NOTIONAL')])
def test_invalid_rules(price, qty, code):
    with pytest.raises(ValueError, match=code): rules().validate_order(price, qty)

def test_status_blocks_quotes():
    with pytest.raises(ValueError, match='not quotable'): PairRules.from_raw({**RAW, 'status':'CANCEL_ONLY'}).validate_order(Decimal('100'), Decimal('0.1'))
