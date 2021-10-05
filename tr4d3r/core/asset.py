"""
Asset components.
"""
from tr4d3r.core import Loggable
from tr4d3r.utils.misc import autostamp
from pprint import pformat
from datetime import datetime
from abc import abstractmethod


class Asset(Loggable):
    """
    Anything of value.
    """
    def __init__(self, name, quantity):
        self._name = name
        self._quantity = quantity
    
    @property
    def name(self):
        return self._name
    
    @property
    def quantity(self):
        return self._quantity
    
    @quantity.setter
    def quantity(self, value):
        assert value >= 0.0, f"Expecting non-negative value, got {value}"
        self._quantity = value
    
    def check(self, other):
        assert isinstance(other, self.__class__)
        assert self.name == other.name, f"Conflicting asset name: {self.name} vs. {other.name}"
    
    @abstractmethod
    def worth(self):
        pass
    
    @property
    def cost(self):
        pass
    
    
class Cash(Asset):
    """
    Whatever is used for purchases and for measuring value.
    """
    def __init__(self, name, quantity):
        super().__init__(name, quantity)
    
    def worth(self):
        return self.quantity
        
    def __repr__(self):
        return f"{self.name}: {round(self.quantity, 6)} units"
    
    def to_dict(self):
        data_dict = {
            "class": self.__class__.__name__,
            "name": self.name,
            "quantity": self.quantity
        }
        return data_dict
    
    @classmethod
    def from_dict(cls, data_dict):
        burner_dict = data_dict.copy()
        class_name = burner_dict.pop("class")
        name = burner_dict.pop("name")
        quantity = burner_dict.pop("quantity")
        
        # sanity check
        assert class_name == cls.__name__, f"Class name mismatch: {class_name} vs. {cls.__name__}"
        assert len(burner_dict) == 0, f"Expecting no remaining attributes, got {burner_dict.keys}"
        return cls(name, quantity)
        
    def add(self, other):
        if other is None:
            return
        self.check(other)
        self.quantity += other.quantity
        other.quantity = 0
    
    def sub(self, other):
        if other is None:
            return
        self.check(other)
        self.quantity -= other.quantity
        other.quantity = 0
        
        
class Item(Asset):
    """
    Whatever is purchased and has variable value.
    """
    def __init__(self, name, quantity, unit_cost):
        super().__init__(name, quantity)
        self._unit_cost = unit_cost
    
    def __repr__(self):
        return f"{self.name}: {round(self.quantity, 6)} units, cost {round(self.unit_cost, 6)} per unit"
    
    def to_dict(self):
        data = {
            "class": self.__class__.__name__,
            "name": self.name, 
            "quantity": self.quantity, 
            "unit_cost": self.unit_cost}
        return data
    
    @classmethod
    def from_dict(cls, data_dict):
        burner_dict = data_dict.copy()
        class_name = burner_dict.pop("class")
        name = burner_dict.pop("name")
        quantity = burner_dict.pop("quantity")
        unit_cost = burner_dict.pop("unit_cost")
        
        # sanity check
        assert class_name == cls.__name__, f"Class name mismatch: {class_name} vs. {cls.__name__}"
        assert len(burner_dict) == 0, f"Expecting no remaining attributes, got {burner_dict.keys()}"
        return cls(name, quantity, unit_cost)
    
    @property
    def unit_cost(self):
        return self._unit_cost
    
    @unit_cost.setter
    def unit_cost(self, value):
        assert value >= 0.0, f"Expecting non-negative value, got {value}"
        self._unit_cost = value
        
    def cost(self):
        return self.unit_cost * self.quantity
    
    def worth(self, *args, **kwargs):
        return self.unit_price(*args, **kwargs) * self.quantity
    
    def bid_worth(self, *args, **kwargs):
        return self.bid_price(*args, **kwargs) * self.quantity
        
    def ask_worth(self, *args, **kwargs):
        return self.ask_price(*args, **kwargs) * self.quantity
    
    @abstractmethod
    def unit_price(self, *args, **kwargs):
        pass
    
    @abstractmethod
    def bid_price(self, *args, **kwargs):
        pass
    
    @abstractmethod
    def ask_price(self, *args, **kwargs):
        pass
    
    def add(self, other):
        if other is None:
            return
        self.check(other)
        total_cost = self.cost() + other.cost()
        total_quantity = self.quantity + other.quantity
        average_unit_cost = total_cost / total_quantity
        self.quantity = total_quantity
        self.unit_cost = average_unit_cost
        other.quantity = 0
    
    def sub(self, other):
        if other is None:
            return
        self.check(other)
        self.quantity -= other.quantity
        other.quantity = 0
    

class PseudoTimeItem(Item):
    """
    Item for pseudo-time simulation where the market can be a variable.
    """
    from .market import PseudoTimeMarket
    COMPATIBLE_MARKETS = {
        PseudoTimeMarket,
    }
    
    def __init__(self, name, quantity, unit_cost, market):
        super().__init__(name, quantity, unit_cost)
        
        # sanity check: market must be None or from compatible classes
        valid_market = bool(market is None)
        for _cls in self.__class__.COMPATIBLE_MARKETS:
            if isinstance(market, _cls):
                valid_market = True
        assert valid_market, f"Unexpected market type: {market.__class__}"
        self._market = market
    
    def to_dict(self):
        data = {"name": self.name, "quantity": self.quantity, "unit_cost": self.unit_cost, "market": self._market}
        return data
    
    @classmethod
    def from_dict(cls, data_dict):
        burner_dict = data_dict.copy()
        name = burner_dict.pop("name")
        quantity = burner_dict.pop("quantity")
        unit_cost = burner_dict.pop("unit_cost")
        market = burner_dict.pop("market")
        assert len(burner_dict) == 0, f"Expecting no remaining attributes, got {burner_dict.keys()}"
        return cls(name, quantity, unit_cost, market)
    
    def unit_price(self, time):
        if self._market is None:
            return 0.0
        return self._market.get_price(self.name, time=time)

    def bid_price(self, time):
        if self._market is None:
            return 0.0
        return self._market.get_bid_price(self.name, time=time)

    def ask_price(self, time):
        if self._market is None:
            return 0.0
        return self._market.get_ask_price(self.name, time=time)

