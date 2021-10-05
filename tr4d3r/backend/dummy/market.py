import math
from numpy.random import default_rng
from datetime import datetime, timedelta, timezone
from pprint import pformat
from tr4d3r.core.market import PseudoTimeMarket
from tr4d3r.utils.misc import autodatetime
from tr4d3r.utils.random import exponential_random_walk


class DummyPseudoTimeMarket(PseudoTimeMarket):
    """A fake market of exponential random walks.
    """
    START_TIME = datetime.strptime('20160101 00:00:00', '%Y%m%d %H:%M:%S').astimezone(timezone.utc)
    END_TIME = datetime.strptime('20220101 00:00:00', '%Y%m%d %H:%M:%S').astimezone(timezone.utc)
    TICK_PERIOD = 10
    STEPS = math.floor((END_TIME - START_TIME).total_seconds() / TICK_PERIOD) - 1
    
    INITIAL_LISTING = {
        'Gold': {'price': 100.0, 'volatility': 1e-5},
        'Stock-1': {'price': 10.0, 'volatility': 3e-5},
        'Stock-2': {'price': 10.0, 'volatility': 3e-5},
        'Coin-1': {'price': 1.0, 'volatility': 1e-4},
        'Coin-2': {'price': 1.0, 'volatility': 1e-4},
        'Coin-3': {'price': 1.0, 'volatility': 1e-4},
    }
    CURRENCY = 'USD'
    
    def __init__(self, seed=0):
        self.rng = default_rng(seed=seed)
        steps = self.__class__.STEPS
        self.price_history = {
            _name: exponential_random_walk(
                self.rng, 
                _attr['price'], 
                self.__class__.STEPS, 
                loc=0.0, 
                scale=_attr['volatility'] * self.__class__.TICK_PERIOD,
            ) for _name, _attr in self.__class__.INITIAL_LISTING.items()
        }
   
    def __repr__(self):
        info = {
            'listing': list(self.price_history.keys()),
            'timespan': [
                self.__class__.START_TIME.strftime('%Y%m%d %H:%M'),
                self.__class__.END_TIME.strftime('%Y%m%d %H:%M'),
            ],
            'tick_period': self.__class__.TICK_PERIOD,
        }
        return f"===={self.__class__.__name__}====\n{pformat(info)}"
    
    def time_sequence(self, offset):
        offset_list = super().time_sequence(offset)
        return [self.__class__.START_TIME + _off for _off in offset_list]
        
    def get_price(self, symbol, time=None):
        time = autodatetime(time)
        past_seconds = (time - self.__class__.START_TIME).total_seconds()
        index = math.floor(past_seconds / self.__class__.TICK_PERIOD)
        assert symbol in self.price_history, f"Unrecognized item {symbol}"
        history = self.price_history[symbol]
        return history[min(index, len(history)-1)]
    