import wrappy
import numpy as np
import pandas as pd
import robin_stocks.robinhood as rh
import math
from tqdm import tqdm
from datetime import datetime, timezone, timedelta
from pprint import pformat
from tr4d3r.core.market import PseudoTimeMarket, RealTimeMarket
from tr4d3r.utils.misc import autodatetime


@wrappy.memoize(cache_limit=100, return_copy=False, persist_path='robin-history.pkl', persist_batch_size=1)
def rh_historicals(symbol, interval, span):
    """
    Helper function for the RobinhoodPseudoTime class.
    """
    rh.login()
    dictl = rh.get_stock_historicals(symbol, interval=interval, span=span)
    assert isinstance(dictl, list) and dictl, f"Expected non-empty list of dicts, got {dictl}"
    assert isinstance(dictl[0], dict), f"Expected non-empty list of dicts, got {dictl}"
    return dictl

def rh_str_to_datetime(utc_str):
    raw_dt = datetime.strptime(utc_str, '%Y-%m-%dT%H:%M:%SZ')
    utc_dt = raw_dt.astimezone(timezone.utc)
    return utc_dt

class RobinhoodPseudoMarket(PseudoTimeMarket):
    """
    Robinhood pseudo-time market where orders can take place in the past.
    This is for simulation purposes.
    """
    CURRENCY = 'USD'
    
    def __init__(self, symbols, interval='day', span='5year'):
        assert len(symbols) > 0, "Expecting at least one symbol"
        self.span = span
        self.interval = interval
        
        self.symbol_to_table = {}
        for _symbol in tqdm(symbols, desc="Loading stock historicals"):
            _dictl = rh_historicals(_symbol, interval, span)
            _table = pd.DataFrame(_dictl)
            _table['begins_at'] = _table['begins_at'].apply(rh_str_to_datetime)
            _table['begins_at_timestamp'] = _table['begins_at'].apply(lambda x: x.timestamp())
            self.symbol_to_table[_symbol] = _table
        
        first_table = self.symbol_to_table[symbols[0]]
        last_idx = first_table.shape[0] - 1
        self.start_time = first_table.loc[0, 'begins_at']
        self.end_time = first_table.loc[last_idx, 'begins_at']
        
    def __repr__(self):
        info = {
            'listing': list(self.symbol_to_table.keys()),
            'timespan': self.span,
            'interval': self.interval,
        }
        return f"===={self.__class__.__name__}====\n{pformat(info)}"
    
    def time_sequence(self, offset):
        offset_list = super().time_sequence(offset)
        return [self.start_time + _off for _off in offset_list]
        
    def get_price(self, symbol, time=None):
        table = self.symbol_to_table[symbol]
        time = autodatetime(time)
        
        # find the most recent recorded time before the supplied time
        interval_idx = np.searchsorted(table['begins_at_timestamp'].values, time.timestamp()+1e-6) - 1
        assert interval_idx >= 0, f"Time out of range: {time}"
        
        return float(table.loc[interval_idx, 'open_price'])

    
class RobinhoodRealMarket(RealTimeMarket):
    """
    Robinhood real-time market.
    """
    MIN_TRANS_AMOUNT = 1e-2
    MIN_TRANS_SHARES = 1e-6
    
    def __init__(self):
        pass
    
    @classmethod
    def round_shares(cls, shares):
        return math.floor(shares / cls.MIN_TRANS_SHARES) * cls.MIN_TRANS_SHARES
        
    @classmethod
    def round_amount(cls, amount):
        return math.floor(amount / cls.MIN_TRANS_AMOUNT) * cls.MIN_TRANS_AMOUNT
        
    def validate_order(self, symbol, shares, amount):
        # check symbol exists in the market
        price = self.get_price(symbol)
        
        # consistency between shares and amount
        if shares is not None:
            assert amount is None, "Expected either shares or amount, got both"
            assert isinstance(shares, float), f"Invalid shares: {shares}"
            amount = shares * price
        else:
            assert amount is not None, "Expected either shares or amount, got neither"
        
        amount = self.__class__.round_amount(amount)
        shares = self.__class__.round_shares(amount / price)
        
        if shares < self.__class__.MIN_TRANS_SHARES or amount < self.__class__.MIN_TRANS_AMOUNT:
            return dict(symbol=symbol, shares=0.0, amount=None, valid=False)
        else:
            return dict(symbol=symbol, shares=shares, amount=None, valid=True)
            
    def market_buy(self, symbol, shares=None, amount=None, **kwargs):
        validate_dict = self.validate_order(symbol, shares, amount)
        if validate_dict['valid']:
            order = rh.orders.order_buy_fractional_by_quantity(symbol, validate_dict['shares'], **kwargs)
        else:
            order = None
        return order
    
    def market_sell(self, symbol, shares=None, amount=None, **kwargs):
        validate_dict = self.validate_order(symbol, shares, amount)
        if validate_dict['valid']:
            order = rh.orders.order_sell_fractional_by_quantity(symbol, validate_dict['shares'], **kwargs)
        else:
            order = None
        return order
    
    def get_price(self, symbol):
        price_list = rh.stocks.get_latest_price(symbol, includeExtendedHours=False)
        return list(map(float, price_list))[0]
    
    def get_bid_price(self, symbol):
        price_list = rh.stocks.get_latest_price(symbol, 'bid_price', includeExtendedHours=False)
        return list(map(float, price_list))[0]
    
    def get_ask_price(self, symbol, time=None):
        price_list = rh.stocks.get_latest_price(symbol, 'ask_price', includeExtendedHours=False)
        return list(map(float, price_list))[0]
    