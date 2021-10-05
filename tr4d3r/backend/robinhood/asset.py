"""
Specialized assets in the Robinhood scenario.
"""
from tr4d3r.core.asset import Item
from tr4d3r.utils.misc import timed_lru_cache
from .utils import symbol_to_market_mic
import robin_stocks.robinhood as rh


class RobinhoodRealItem(Item):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.market_mic = symbol_to_market_mic(self.name)
    
    @classmethod
    def from_rh_holding(cls, symbol, data_dict):
        quantity = data_dict["quantity"]
        unit_cost = data_dict["average_buy_price"]
        return cls(symbol, quantity, unit_cost)
    
    @timed_lru_cache(seconds=60)
    def unit_price(self):
        price_list = rh.get_latest_price(self.name, includeExtendedHours=True)
        return list(map(float, price_list))[0]
    
    @timed_lru_cache(seconds=60)
    def bid_price(self):
        price_list = rh.get_latest_price(self.name, 'bid_price')
        return list(map(float, price_list))[0]
    
    @timed_lru_cache(seconds=60)
    def ask_price(self):
        price_list = rh.get_latest_price(self.name, 'ask_price')
        return list(map(float, price_list))[0]
    
    