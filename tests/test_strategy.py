from decimal import Decimal
from polyester_bot.models import AssetBalance, Side
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

def balance_rules():
    return PairRules.from_raw(dict(symbol='BTC-USDT',symbolId=1,status='ENABLED',tickSize='0.01',stepSize='0.001',minQtyBase='0.01',minNotionalQuote='5',baseAssetId=10,quoteAssetId=20))

def test_balance_sizing_is_independent_per_side():
    rules = balance_rules()
    balances = {20: AssetBalance(20, Decimal('5.50')), 10: AssetBalance(10, Decimal('0.060'))}
    quotes = MarketMaker('BTC-USDT', Decimal('1'), Decimal('20'), Decimal('1')).quotes(rules, Decimal('100'), Decimal('101'), [], balances)
    by_side = {quote.side: quote for quote in quotes}
    assert by_side[Side.BUY].qty == Decimal('0.054')
    assert by_side[Side.SELL].qty == Decimal('0.060')

def test_missing_balance_suppresses_only_affected_side():
    rules = balance_rules()
    balances = {20: AssetBalance(20, Decimal('10'))}
    quotes = MarketMaker('BTC-USDT', Decimal('0.1'), Decimal('20'), Decimal('1')).quotes(rules, Decimal('100'), Decimal('101'), [], balances)
    assert [quote.side for quote in quotes] == [Side.BUY]

def test_quote_notional_cap_limits_both_sides():
    rules = balance_rules()
    balances = {20: AssetBalance(20, Decimal('1000')), 10: AssetBalance(10, Decimal('100'))}
    quotes = MarketMaker('BTC-USDT', Decimal('1'), Decimal('20'), Decimal('10'), quote_notional_cap=Decimal('6')).quotes(rules, Decimal('100'), Decimal('101'), [], balances)
    assert all(quote.price * quote.qty <= Decimal('6') for quote in quotes)
