import pytest
from polyester_bot.storage import Store

@pytest.mark.asyncio
async def test_restart_recovers_open_orders(tmp_path):
    path = str(tmp_path / 'bot.db'); s = Store(path); await s.open()
    await s.upsert_order({'order_id':'o1','client_order_id':'c1','symbol':'BTC-USDT','side':'buy','price':'100','qty':'0.1','filled_qty':'0.02','status':'partially_filled','updated_at':'now'}); await s.close()
    s2 = Store(path); await s2.open(); rows = await s2.open_orders('BTC-USDT'); await s2.close()
    assert rows[0]['filled_qty'] == '0.02'
