from tr4d3r.core import Loggable
from tr4d3r.core.asset import Item
from tr4d3r.core.mechanism import NamedCallback, Tentative
from tr4d3r.utils.misc import datetime_to_string, string_to_datetime, utcnow
from pprint import pformat
from datetime import datetime
from collections import defaultdict
from abc import abstractmethod
import wrappy
import dill as pickle


class EquilibriumPortfolioManager(Loggable):
    """
    Manages any number of portfolios with
        - a fixed set of items considered for trading;
        - an adjustable target ratio in terms of total worth, for each item.
    """
    # daily progression of 3%, capped at 50% for any time gap
    DEFAULT_PROGRESSION_FUNC = lambda t: min(0.5, 0.03 * (t / 86400))
    
    def __init__(self, equilibrium, params=None):
        """
        equilibrium: symbol -> target_ratio dict.
        """
        self._initial_equilibrium = equilibrium.copy()
        self._running_equilibrium = equilibrium.copy()
        self.params = params or {}
    
    def __repr__(self):
        return self.params.get('name', self.__class__.__name__)
    
    @property
    def initial_equilibrium(self):
        return self._initial_equilibrium
    
    @property
    def equilibrium(self):
        return self._running_equilibrium
    
    @equilibrium.setter
    def equilibrium(self, equil_dict):
        self._info(f"Setting new equilibrium {equil_dict}")
        assert sum(equil_dict.values()) <= 1.0 - self.params.get('cash_ratio', 0.03), "Too much total ratio for items"
        self._running_equilibrium = equil_dict.copy()
    
    def linear_update(self, equil_dictl, coefficients):
        """
        Update the running equilibrium as a linear combination of equilibria.
        """
        # initialize unnormalized linear combination
        raw_combination = defaultdict(float)
        total_coeff = 0.0
        
        # collect weighted ratios for each symbol
        for _dict, _coeff in zip(equil_dictl, coefficients):
            # the total ratio supplied by each equil_dict must not exceed 1.0-cash
            _total_ratio = 0.0
            for _symbol, _ratio in _dict.items():
                assert _ratio >= 0.0, f"Expected non-negative ratio, got {_ratio}"
                if _ratio > 0.0:
                    raw_combination[_symbol] += _ratio * _coeff
                    _total_ratio += _ratio
            assert _total_ratio <= 1.0 - self.params.get('cash_ratio', 0.03), "Too much total ratio for items"
            total_coeff += _coeff
        
        # normalize and set as new equilibrium
        new_equilibrium = {_k: _v / total_coeff for _k, _v in raw_combination.items()}
        self.equilibrium = new_equilibrium
        
    @abstractmethod
    def tick_read(self, folio, **kwargs):
        pass
    
    @abstractmethod
    def tick_write(self, folio, **kwargs):
        pass
    
    @classmethod
    def load_pickle(cls, pkl_path):
        with open(pkl_path, 'rb') as f:
            pkl_dict = pickle.load(f)
        equil_dict = pkl_dict['equilibrium']
        param_dict = pkl_dict['params']
        return cls(equil_dict, param_dict)
    
    def dump_pickle(self, pkl_path):
        pkl_dict = {
            'equilibrium': self.equilibrium,
            'params': self.params,
        }
        with open(pkl_path, 'wb') as f:
            pickle.dump(pkl_dict, f)
    
    
class PseudoTimeEquilibrium(EquilibriumPortfolioManager):
    def tick_read(self, folio, time):
        """
        Gather data for analysis.
        """
        worth = folio.worth(time)
        data = {
            'time': time,
            'principal': folio.principal.quantity,
            'worth': worth,
            '% cash': 100 * folio.cash.worth() / worth,
        }
        for _symbol in self.equilibrium.keys():
            data[f"P:{_symbol}"] = folio.market.get_price(_symbol, time)
            data[f"Q:{_symbol}"] = folio[_symbol].quantity
            data[f"C:{_symbol}"] = folio[_symbol].unit_cost
            data[f"% {_symbol}"] = 100 * folio[_symbol].worth(time) / worth
        
        return data
        
    def tick_write(self, folio, time):
        """
        Make trading decisions and update the last time of making moves.
        """
        gap_seconds = folio.tick(time)
        for _symbol, _ratio in self.equilibrium.items():
            # determine if item exists and then its worth
            _item = folio[_symbol]
            _item_exists = _item.name == _symbol
            _bid_worth = _item.bid_worth(time) if _item_exists else 0.0
            _ask_worth = _item.ask_worth(time) if _item_exists else 0.0
            
            # determine "step size"
            _target_worth = _ratio * folio.worth(time)
            _step = self.params.get('progression_func', self.__class__.DEFAULT_PROGRESSION_FUNC)(gap_seconds)
            assert _step <= 1.0, f"Step size too large: {_step}"
            
            # market orders toward equilibrium
            # ask_worth is always above bid_worth
            if _target_worth > _ask_worth:
                _amount = (_target_worth - _ask_worth) * _step
                folio.market_buy(_symbol, amount=_amount, time=time)
            elif _item_exists and _target_worth < _bid_worth:
                _amount = (_bid_worth - _target_worth) * _step
                folio.market_sell(_symbol, amount=_amount, time=time)
            else:
                pass
            

class RealTimeEquilibrium(EquilibriumPortfolioManager):
    def tick_read(self, folio):
        """
        Gather data for analysis.
        """
        worth = folio.worth()
        data = {
            'time': utcnow(),
            'principal': folio.principal.quantity,
            'worth': worth,
            '% cash': 100 * folio.cash.worth() / worth,
        }
        for _symbol in self.equilibrium.keys():
            _price = folio.market.get_price(_symbol)
            _quantity = folio[_symbol].quantity
            data[f"P:{_symbol}"] = _price
            data[f"Q:{_symbol}"] = _quantity
            data[f"C:{_symbol}"] = folio[_symbol].unit_cost
            data[f"% {_symbol}"] = 100 * (_price * _quantity) / worth
        
        return data
        
    def tick_write(self, folio, execute=False):
        """
        Make trading decisions and update the last time of making moves.
        """
        prev_datetime = datetime_to_string(folio.last_tick_time)
        gap_seconds = folio.tick(update=execute)
        self._info(f"Gap {gap_seconds} seconds since {prev_datetime}")
        folio_worth = folio.worth()
        open_order_values = folio.open_order_values()
        for _symbol, _ratio in self.equilibrium.items():
            # determine if item exists and then its worth
            _item = folio[_symbol]
            _item_exists = _item.name == _symbol
            _ava_worth = _item.worth() if _item_exists else 0.0
            _bid_worth = _item.bid_worth() if _item_exists else 0.0
            _ask_worth = _item.ask_worth() if _item_exists else 0.0
            # adjust estimated worth based on open order
            _ord_worth = open_order_values[_symbol]
            _cur_worth = _ava_worth + _ord_worth
            _bid_worth += _ord_worth
            _ask_worth += _ord_worth
            
            # determine "step size"
            _cur_ratio = _cur_worth / folio_worth
            _target_worth = _ratio * folio_worth
            _step = self.params.get('progression_func', self.__class__.DEFAULT_PROGRESSION_FUNC)(gap_seconds)
            assert _step <= 1.0, f"Step size too large: {_step}"
            
            # market orders toward equilibrium
            # ask_worth is always above bid_worth
            self._info(f"{_symbol} worth : tar. {round(_target_worth, 2)} ({round(_ratio*100, 2)}%) | cur. {round(_cur_worth, 2)} ({round(_cur_ratio*100, 2)}%)")
            self._info(f"{_symbol} worth : ava. {round(_ava_worth, 6)} | ord. {round(_ord_worth, 2)} | bid-ask {round(_bid_worth, 2)}-{round(_ask_worth, 2)}")
            if _target_worth > _ask_worth:
                _amount = (_target_worth - _cur_worth) * _step
                _action = 'market buy'
                _func = folio.market_buy
            elif _item_exists and _target_worth < _bid_worth:
                _amount = (_cur_worth - _target_worth) * _step
                _action = 'market sell'
                _func = folio.market_sell
            else:
                self._info(f"{_symbol} near equilibrium, staying put.")
                return gap_seconds
            
            _base_msg = f"{_action}: {_symbol} | {round(_amount, 6)} {folio.cash.name}"
            if execute:
                info = _func(_symbol, amount=_amount)
                self._warn(f"Real {_base_msg}\n{info}")
            else:
                self._info(f"Fake {_base_msg}")
            
        return gap_seconds