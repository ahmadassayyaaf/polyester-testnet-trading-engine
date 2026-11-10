import pytest
from polyester_bot.storage import Store

@pytest.mark.asyncio
async def test_restart_recovers_open_orders(tmp_path):
    path = str(tmp_path / 'bot.db'); s = Store(path); await s.open()
    await s.upsert_order({'order_id':'o1','client_order_id':'c1','symbol':'BTC-USDT','side':'buy','price':'100','qty':'0.1','filled_qty':'0.02','status':'partially_filled','updated_at':'now'}); await s.close()
    s2 = Store(path); await s2.open(); rows = await s2.open_orders('BTC-USDT'); await s2.close()
    assert rows[0]['filled_qty'] == '0.02'

@pytest.mark.asyncio
async def test_stale_order_version_cannot_overwrite_newer_state(tmp_path):
    s = Store(str(tmp_path / 'versioned.db')); await s.open()
    base = {'order_id':'o1','client_order_id':'mm-bid-1','symbol':'BTC-USDT','side':'buy','price':'100','qty':'0.1','filled_qty':'0','status':'working','updated_at':'new','order_version':2}
    await s.upsert_order(base)
    stale = dict(base, filled_qty='0.01', status='pending', updated_at='old', order_version=1)
    await s.upsert_order(stale)
    rows = await s.open_orders('BTC-USDT')
    await s.close()
    assert rows[0]['filled_qty'] == '0'
    assert rows[0]['status'] == 'working'
    assert rows[0]['order_version'] == 2

@pytest.mark.asyncio
async def test_owned_orders_filters_prefix(tmp_path):
    s = Store(str(tmp_path / 'owned.db')); await s.open()
    common = {'symbol':'BTC-USDT','side':'buy','price':'100','qty':'0.1','filled_qty':'0','status':'working','updated_at':'now'}
    await s.upsert_order(dict(common, order_id='owned', client_order_id='mm-bid-1'))
    await s.upsert_order(dict(common, order_id='other', client_order_id='external-1'))
    rows = await s.owned_orders('BTC-USDT', 'mm-')
    await s.close()
    assert [row['client_order_id'] for row in rows] == ['mm-bid-1']
