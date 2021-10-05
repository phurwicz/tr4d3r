from tr4d3r.core import Loggable
from tr4d3r.core.asset import Cash, Item, PseudoTimeItem
from tr4d3r.core.mechanism import NamedCallback, Tentative
from tr4d3r.utils.misc import autostamp, datetime_to_string, string_to_datetime, utcnow
from pprint import pformat
from datetime import datetime
from abc import abstractmethod
import wrappy
import json


class Portfolio(Loggable):
    """
    Base class for portfolios.
    """
    
    DEFAULT_CASH_CLASS = Cash
    DEFAULT_ITEM_CLASS = Item
    DUMMY_ITEM = Item('NULL', quantity=0.0, unit_cost=0.0)
    DEFAULT_GAP_SECONDS = 86400
    
    def __init__(self, principal, cash, items, **kwargs):
        # initialize holdings and other stats
        assert isinstance(principal, Cash)
        assert isinstance(cash, Cash)
        self.principal = principal
        self.cash = cash
        self.item_dict = dict()
        for _item in items:
            assert isinstance(_item, Item)
            self.add_item(_item)
        self.last_tick_time = kwargs.get('last_tick_time', None)
        
        # initialize support parameters
        self.verbose = kwargs.get('verbose', None)
        
        # initialize portfolio management data structure
        self._callbacks = []
       
    def __repr__(self):
        return pformat(self.to_dict())
    
    def __getitem__(self, symbol):
        return self.item_dict.get(symbol, self.__class__.DUMMY_ITEM)
    
    def to_dict(self):
        data_dict = {
            "class": self.__class__.__name__,
            "last_tick_time": self.last_tick_time,
            "principal": self.principal.to_dict(),
            "cash": self.cash.to_dict(),
            "items": {_item.name: _item.to_dict() for _item in sorted(self.item_dict.values(), key=lambda x: x.name)},
        }
        return data_dict
    
    @classmethod
    def from_dict(cls, data_dict):
        burner_dict = data_dict.copy()
        class_name = burner_dict.pop("class")
        prin_dict = burner_dict.pop("principal")
        cash_dict = burner_dict.pop("cash")
        items_dict = burner_dict.pop("items")
        
        # sanity check
        assert class_name == cls.__name__, f"Class name mismatch: {class_name} vs. {cls.__name__}"
        
        # constructor
        principal = cls.DEFAULT_CASH_CLASS.from_dict(prin_dict)
        cash = cls.DEFAULT_CASH_CLASS.from_dict(cash_dict)
        items = [cls.DEFAULT_ITEM_CLASS.from_dict(_item_d) for _item_d in items_dict.values()]
        return cls(principal, cash, items, **burner_dict)
       
    def dump_json(self, path):
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=4)
        return path
            
    @classmethod
    def load_json(cls, path):
        with open(path, 'r') as f:
            folio = cls.from_dict(json.load(f))
        return folio
           
    @abstractmethod
    def worth(self, *args, **kwargs):
        pass
           
    @abstractmethod
    def worth_detail(self, *args, **kwargs):
        pass
    
    def cost(self):
        value = self.principal.worth()
        for _item in self.item_dict.values():
            value += _item.cost()
        return value
           
    def cost_detail(self):
        detail = {
            "total": self.cost(),
            "cash": self.principal.__repr__(),
            "items": [{"name": _item.name, "cost": _item.cost(time)} for _item in self.item_dict.values()],
        }
        return detail
    
    def add_item(self, item):
        """
        Add an item to the portfolio.
        """
        name = item.name
        if name in self.item_dict:
            self.item_dict[name].add(item)
        else:
            self.item_dict[name] = item
    
    def sub_item(self, item):
        """
        Subtract an item from the portfolio.
        """
        name = item.name
        if name in self.item_dict:
            self.item_dict[name].sub(item)
            self.check(name)
        else:
            raise KeyError(f"Item {name} does not exist in the portfolio.")
            
    def check(self, name):
        """
        Remove an item if its quantity is numerically zero.
        """
        if name in self.item_dict:
            quantity = self.item_dict[name].quantity
            if -1e-16 < quantity < 1e-16:
                self.item_dict.pop(name)
            elif quantity <= -1e-16:
                raise ValueError(f"Invalid quantity: {quantity} of {name}")
            else:
                pass
            
    @abstractmethod
    def flush_callbacks(self, *args, **kwargs):
        pass

    @abstractmethod
    def tick(self, *args, **kwargs):
        pass

    @abstractmethod
    def deposit(self, amount, **kwargs):
        pass

    @abstractmethod
    def withdraw(self, amount, **kwargs):
        pass

    @abstractmethod
    def market_buy(self, symbol, shares=None, amount=None, **kwargs):
        pass

    @abstractmethod
    def market_sell(self, symbol, shares=None, amount=None, **kwargs):
        pass

    
class PseudoTimePortfolio(Portfolio):
    """
    Portfolio specifically for pseudo-time simulation.
    """
    
    DEFAULT_CASH_CLASS = Cash
    DEFAULT_ITEM_CLASS = PseudoTimeItem
    DUMMY_ITEM = PseudoTimeItem('NULL', quantity=0.0, unit_cost=0.0, market=None)
    DEFAULT_GAP_SECONDS = 86400
    
    def __init__(self, principal, cash, items, market, **kwargs):
        super().__init__(principal, cash, items, **kwargs)
        if isinstance(self.last_tick_time, str):
            self.last_tick_time = string_to_datetime(self.last_tick_time)
        self.market = market
            
    @classmethod
    def from_dict(cls, data_dict):
        burner_dict = data_dict.copy()
        class_name = burner_dict.pop("class")
        prin_dict = burner_dict.pop("principal")
        cash_dict = burner_dict.pop("cash")
        items_dict = burner_dict.pop("items")
        market = burner_dict.pop("market")
        
        # sanity check
        assert class_name == cls.__name__, f"Class name mismatch: {class_name} vs. {cls.__name__}"
        
        # constructor
        principal = cls.DEFAULT_CASH_CLASS.from_dict(prin_dict)
        cash = cls.DEFAULT_CASH_CLASS.from_dict(cash_dict)
        items = [cls.DEFAULT_ITEM_CLASS.from_dict(_item_d) for _item_d in items_dict.values()]
        return cls(principal, cash, items, market, **burner_dict)
       
    def worth(self, time):
        value = self.cash.worth()
        for _item in self.item_dict.values():
            value += _item.worth(time)
        return value
    
    def worth_detail(self, time):
        detail = {
            "total": self.worth(time),
            "cash": self.cash.__repr__(),
            "items": [{"name": _item.name, "worth": _item.worth(time)} for _item in self.item_dict.values()],
        }
        return detail
        
    def deposit(self, amount, time):
        self.principal.quantity += amount
        self.cash.quantity += amount
        self._info(f"Cash deposit {amount} @ {time} | balance = {self.cash.quantity}")

    def withdraw(self, amount, time):
        self.principal.quantity -= amount
        self.cash.quantity -= amount
        self._info(f"Cash withdrawal {amount} @ {time} | balance = {self.cash.quantity}")

    def tick(self, time):
        gap_seconds = self.__class__.DEFAULT_GAP_SECONDS if self.last_tick_time is None else (time - self.last_tick_time).total_seconds()
        assert gap_seconds > 0, f"Unexpected timeline: last move @ {self.last_tick_time}, tick @ {time}"
        self.last_tick_time = time
        return gap_seconds
        
    def market_buy(self, symbol, shares=None, amount=None, time=None):
        time = autostamp(time)
        item, cash = self.market.market_ask(symbol, shares=shares, amount=amount, time=time)
        if self.verbose:
            self._good(f"{datetime.fromtimestamp(time)}: B {round(item.quantity, 6)} {item.name} <- {round(cash.quantity, 6)} {cash.name}.")
        self.cash.sub(cash)
        self.add_item(item)
    
    def market_sell(self, symbol, shares=None, amount=None, time=None):
        time = autostamp(time)
        item, cash = self.market.market_bid(symbol, shares=shares, amount=amount, time=time)
        if self.verbose:
            self._good(f"{datetime.fromtimestamp(time)}: S {round(item.quantity, 6)} {item.name} -> {round(cash.quantity, 6)} {cash.name}.")
        self.sub_item(item)
        self.cash.add(cash)
        self.check(item.name)
    
    def limit_buy(self, symbol, shares, limit_price, order_time=None, expire_after=86400):
        
        def condition_f(time):
            price = self.market.get_ask_price(symbol, time=time)
            return bool(price <= limit_price)
        
        def trigger_f(time):
            self.market_buy(symbol, shares=shares, time=time)
            
        condition = NamedCallback(
            condition_f, 
            f"{symbol} P<={round(limit_price, 6)}"
        )
        trigger = NamedCallback(
            trigger_f,
            f"B {round(shares, 6)} * {symbol}"
        )
        callback = Tentative(
            condition=condition,
            trigger=trigger,
            order_time=autostamp(order_time),
            expire_after=86400,
        )
        
        self._callbacks.append(callback)
    
    def limit_sell(self, symbol, shares, limit_price, order_time=None, expire_after=86400):
        
        def condition_f(time):
            price = self.market.get_bid_price(symbol, time=time)
            return bool(price >= limit_price)
        
        def trigger_f(time):
            self.market_sell(symbol, shares=shares, time=time)
            
        condition = NamedCallback(
            condition_f, 
            f"{symbol} P>={round(limit_price, 6)}"
        )
        trigger = NamedCallback(
            trigger_f,
            f"S {round(shares, 6)} * {symbol}"
        )
        callback = Tentative(
            condition=condition,
            trigger=trigger,
            order_time=autostamp(order_time),
            expire_after=86400,
        )
        
        self._callbacks.append(callback)

    def flush_callbacks(self, time):
        callbacks = self._callbacks[:]
        self._callbacks.clear()
        
        for _callback in callbacks:
            _done = _callback(time)
            if not _done:
                self._callbacks.append(_callback)


class RealTimePortfolio(Portfolio):
    """
    Base class for portfolios for real-time trading.
    """
    DEFAULT_GAP_SECONDS = 86400
    
    def __init__(self, principal, cash, items, open_orders, **kwargs):
        super().__init__(principal, cash, items, **kwargs)
        if isinstance(self.last_tick_time, str):
            self.last_tick_time = string_to_datetime(self.last_tick_time)
        # real-time portfolios have open orders that get closed later
        self._open_orders = set(open_orders)
       
    def to_dict(self):
        data_dict = {
            "class": self.__class__.__name__,
            "last_tick_time": datetime_to_string(self.last_tick_time),
            "principal": self.principal.to_dict(),
            "cash": self.cash.to_dict(),
            "items": {_item.name: _item.to_dict() for _item in sorted(self.item_dict.values(), key=lambda x: x.name)},
            "open_orders": list(self.open_orders),
        }
        return data_dict
    
    @classmethod
    def from_dict(cls, data_dict):
        burner_dict = data_dict.copy()
        class_name = burner_dict.pop("class")
        prin_dict = burner_dict.pop("principal")
        cash_dict = burner_dict.pop("cash")
        items_dict = burner_dict.pop("items")
        open_orders = burner_dict.pop("open_orders")
        
        # sanity check
        assert class_name == cls.__name__, f"Class name mismatch: {class_name} vs. {cls.__name__}"
        
        # constructor
        principal = cls.DEFAULT_CASH_CLASS.from_dict(prin_dict)
        cash = cls.DEFAULT_CASH_CLASS.from_dict(cash_dict)
        items = [cls.DEFAULT_ITEM_CLASS.from_dict(_item_d) for _item_d in items_dict.values()]
        return cls(principal, cash, items, open_orders, **burner_dict)
       
    @property
    def open_orders(self):
        return self._open_orders
    
    @open_orders.setter
    def open_orders(self, orders):
        raise ValueError("It is forbidden to directly set open orders. Please use set methods such as add() or remove().")
        
    @wrappy.todo("No programmatic deposit implemented at the moment.")
    def deposit(self, amount, **kwargs):
        pass

    @wrappy.todo("No programmatic withdrawal implemented at the moment.")
    def withdraw(self, amount, **kwargs):
        pass

    def worth(self):
        value = self.cash.worth()
        for _item in self.item_dict.values():
            value += _item.worth()
        return value
    
    def worth_detail(self):
        detail = {
            "total": self.worth(),
            "cash": self.cash.__repr__(),
            "items": [{"name": _item.name, "worth": _item.worth()} for _item in self.item_dict.values()],
        }
        return detail
       
    @abstractmethod
    def open_order_values(self):
        """
        Compute the values of open orders for each item symbol.
        Buy -> positive
        Sell -> negative
        """
        pass
        
    def tick(self, update):
        now_utc = utcnow()
        gap_seconds = self.__class__.DEFAULT_GAP_SECONDS if self.last_tick_time is None else (now_utc - self.last_tick_time).total_seconds()
        assert gap_seconds > 0, f"Unexpected timeline: last move @ {self.last_tick_time}, tick @ {now_utc}"
        assert isinstance(update, bool), f"Expected boolean value"
        if update:
            self.last_tick_time = now_utc
        return gap_seconds
        
    def market_buy(self, symbol, shares=None, amount=None, **kwargs):
        order = self.market.market_buy(symbol, shares=shares, amount=amount, **kwargs)
        if order is not None:
            self.open_orders.add(order['id'])
        return order

    def market_sell(self, symbol, shares=None, amount=None, **kwargs):
        order = self.market.market_sell(symbol, shares=shares, amount=amount, **kwargs)
        if order is not None:
            self.open_orders.add(order['id'])
        return order
    
    @abstractmethod
    def refresh_open_orders(self):
        """
        Refresh the state of all open orders.
        """
        pass
    
    def flush_callbacks(self):
        callbacks = self._callbacks[:]
        self._callbacks.clear()
        
        for _callback in callbacks:
            _done = _callback()
            if not _done:
                self._callbacks.append(_callback)
