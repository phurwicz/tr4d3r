"""
Specialized assets in the Robinhood scenario.
"""
from tr4d3r.core.asset import Item
from tr4d3r.utils.misc import timed_lru_cache
from .utils import symbol_to_market_mic
from .market import RobinhoodRealMarket
import robin_stocks.robinhood as rh


class RobinhoodRealItem(Item):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.correct_quantity()
        self.market_mic = symbol_to_market_mic(self.name)

    def correct_quantity(self):
        old_value = self.quantity
        new_value = RobinhoodRealMarket.round_shares(old_value)
        if not new_value == old_value:
            self._warn(f"Rounding quantity {old_value} to {new_value}")
            # DO NOT trigger quantity.setter which will get a loop
            self._quantity = new_value

    def postprocess_quantity(self, value):
        self.correct_quantity()

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
        price_list = rh.get_latest_price(self.name, "bid_price")
        return list(map(float, price_list))[0]

    @timed_lru_cache(seconds=60)
    def ask_price(self):
        price_list = rh.get_latest_price(self.name, "ask_price")
        return list(map(float, price_list))[0]
