"""
Asset components.
"""
from abc import abstractmethod
import pandas as pd
from tr4d3r.core import Loggable
from tr4d3r.utils.misc import autostamp
from datetime import timedelta


class PseudoTimeMarket(Loggable):
    """Abstract base class of markets where one can buy and sell items.
    """
    
    def __init__(self, *args, **kwargs):
        pass
    
    @abstractmethod
    def time_sequence(self, offset):
        pass
    
    @abstractmethod
    def get_price(self, symbol):
        pass
    
    def create_portfolio(self, cash_quantity, **kwargs):
        from .portfolio import PseudoTimePortfolio
        from .asset import Cash
        
        folio = PseudoTimePortfolio(
            principal=Cash(self.__class__.CURRENCY, cash_quantity),
            cash=Cash(self.__class__.CURRENCY, cash_quantity),
            items=[],
            market=self, 
            **kwargs,
        )
        return folio
        
    def time_sequence(self, offset):
        offset_list = list(offset)
        assert len(offset_list) >= 1, "Expected at least one element"
        assert sorted(offset_list) == offset_list, "Offset must be sorted in ascending order"
        first = offset_list[0]
        assert isinstance(first, timedelta), f"Expected timedelta, got {type(first)} {first}"
        return offset_list
        
    def get_bid_price(self, symbol, time=None):
        return self.get_price(symbol, time=time)
    
    def get_ask_price(self, symbol, time=None):
        return self.get_price(symbol, time=time)
    
    def get_shares(self, price, shares=None, amount=None):
        assert isinstance(price, int) or isinstance(price, float), f"Expected price as int or float, got {type(price)} {price}"
        if shares is not None:
            assert amount is None, "Expected exactly one of 'shares' and 'amount'"
            assert isinstance(shares, int) or isinstance(shares, float), f"Expected shares as int or float, got {type(shares)} {shares}"
        else:
            assert isinstance(amount, float), f"Expected amount to be float, got {type(amount)} {amount}"
            shares = float(amount) / float(price)
        return shares
        
    def market_bid(self, symbol, shares=None, amount=None, time=None):
        from .asset import Cash, PseudoTimeItem
        
        price = self.get_bid_price(symbol, time=time)
        shares = self.get_shares(price, shares=shares, amount=amount)
        item = PseudoTimeItem(name=symbol, quantity=shares, unit_cost=price, market=self)
        cash = Cash(name=self.__class__.CURRENCY, quantity=shares*price)
        return item, cash
    
    def market_ask(self, symbol, shares=None, amount=None, time=None):
        from .asset import Cash, PseudoTimeItem
        
        price = self.get_ask_price(symbol, time=time)
        shares = self.get_shares(price, shares=shares, amount=amount)
        item = PseudoTimeItem(name=symbol, quantity=shares, unit_cost=price, market=self)
        cash = Cash(name=self.__class__.CURRENCY, quantity=shares*price)
        return item, cash
        

class RealTimeMarket(Loggable):
    """
    Base class for real-time markets.
    """
    @abstractmethod
    def market_buy(self, symbol, shares=None, amount=None, **kwargs):
        pass
            
    @abstractmethod
    def market_sell(self, symbol, shares=None, amount=None, **kwargs):
        pass
            
    @abstractmethod
    def get_price(self, symbol):
        pass
    
    @abstractmethod
    def get_bid_price(self, symbol, **kwargs):
        pass
    
    @abstractmethod
    def get_ask_price(self, symbol, **kwargs):
        pass
    