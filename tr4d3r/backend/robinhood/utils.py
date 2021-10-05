import re
import robin_stocks.robinhood as rh
from functools import lru_cache


def symbol_to_market_mic(symbol):
    """
    Get the MIC value of the market for a specified symbol.
    """
    markets = rh.get_instruments_by_symbols(symbol, info='market')
    
    if not markets:
        return 'N/A'
    
    assert len(markets) == 1, f"Expecting exactly one market for symbol {symbol}, got {markets}"
    mic = re.search(r'[A-Z]{4}\/$', markets[0]).group()[:-1]
    return mic


@lru_cache(maxsize=1000)
def cached_order_info(order_id):
    """
    A cached version of get_stock_order_info.
    Can be useful for quickly finding invariant attributes
    such as the trade amount or quantity, but not the state.
    """
    order_dict = rh.get_stock_order_info(order_id)
    symbol = rh.get_instrument_by_url(order_dict['instrument'], info='symbol')
    order_dict['symbol'] = symbol
    return order_dict