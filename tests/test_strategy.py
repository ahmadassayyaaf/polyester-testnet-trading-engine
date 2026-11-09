from decimal import Decimal
from polyester_bot.models import Side
from polyester_bot.rules import PairRules
from polyester_bot.strategy import MarketMaker


def test_strategy_produces_two_valid_post_only_quotes():
    rules = PairRules.from_raw(dict(symbol='BTC-USDT',symbolId=1,status='ENABLED',tickSize='0.01',stepSize='0.001',minQtyBase='0.01',minNotionalQuote='5'))
    quotes = MarketMaker('BTC-USDT', Decimal('0.1'), Decimal('20'), Decimal('1')).quotes(rules, Decimal('100'), Decimal('101'), [])
    assert {q.side for q in quotes} == {Side.BUY, Side.SELL}

def test_inventory_limit_suppresses_buy():
    rules = PairRules.from_raw(dict(symbol='BTC-USDT',symbolId=1,status='ENABLED',tickSize='0.01',stepSize='0.001',minQtyBase='0.01',minNotionalQuote='5'))
    maker = MarketMaker('BTC-USDT', Decimal('0.1'), Decimal('20'), Decimal('1')); maker.inventory = Decimal('1')
    assert all(q.side == Side.SELL for q in maker.quotes(rules, Decimal('100'), Decimal('101'), []))
