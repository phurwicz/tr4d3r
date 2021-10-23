from tr4d3r.core import Loggable
from tr4d3r.utils.misc import datetime_to_string, utcnow
from collections import defaultdict
from abc import abstractmethod
import dill as pickle
import wrappy


def capped_daily_progression(seconds, step=0.03, cap=0.5):
    assert 0.0 < step <= 1.0, f"Expected 0.0 < step <= 1.0, got {step}"
    assert 0.0 < cap <= 1.0, f"Expected 0.0 < cap <= 1.0, got {cap}"
    days = seconds / 86400
    return min(cap, step * days)


class EquilibriumPortfolioManager(Loggable):
    """
    Manages any number of portfolios with
        - a fixed set of items considered for trading;
        - an adjustable target ratio in terms of total worth, for each item.
    """

    DEFAULT_PROGRESSION_FUNC = capped_daily_progression

    def __init__(self, equilibrium, params=None):
        """
        equilibrium: symbol -> target_ratio dict.
        """
        self._initial_equilibrium = equilibrium.copy()
        self._running_equilibrium = equilibrium.copy()
        self.params = params or {}

    def __repr__(self):
        return self.params.get("name", self.__class__.__name__)

    @property
    def initial_equilibrium(self):
        return self._initial_equilibrium

    @property
    def equilibrium(self):
        return self._running_equilibrium

    @equilibrium.setter
    def equilibrium(self, equil_dict):
        self._info(f"Setting new equilibrium {equil_dict}")
        assert sum(equil_dict.values()) <= 1.0 - self.params.get(
            "cash_ratio", 0.03
        ), "Too much total ratio for items"
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
            assert _total_ratio <= 1.0 - self.params.get(
                "cash_ratio", 0.03
            ), "Too much total ratio for items"
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
        with open(pkl_path, "rb") as f:
            pkl_dict = pickle.load(f)
        equil_dict = pkl_dict["equilibrium"]
        param_dict = pkl_dict["params"]
        return cls(equil_dict, param_dict)

    def dump_pickle(self, pkl_path):
        pkl_dict = {
            "equilibrium": self.equilibrium,
            "params": self.params,
        }
        with open(pkl_path, "wb") as f:
            pickle.dump(pkl_dict, f)


class PseudoTimeEquilibrium(EquilibriumPortfolioManager):
    def tick_read(self, folio, time):
        """
        Gather data for analysis.
        """
        worth = folio.worth(time)
        data = {
            "time": time,
            "principal": folio.principal.quantity,
            "worth": worth,
            "% cash": 100 * folio.cash.worth() / worth,
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
            _step = self.params.get(
                "progression_func", self.__class__.DEFAULT_PROGRESSION_FUNC
            )(gap_seconds)
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
            "time": utcnow(),
            "principal": folio.principal.quantity,
            "worth": worth,
            "% cash": 100 * folio.cash.worth() / worth,
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

        @wrappy.guard(fallback_retval=0, print_traceback=True)
        def subroutine(symbol, ratio):
            # determine if item exists and then its worth
            item = folio[symbol]
            item_exists = item.name == symbol
            ava_worth = item.worth() if item_exists else 0.0
            bid_worth = item.bid_worth() if item_exists else 0.0
            ask_worth = item.ask_worth() if item_exists else 0.0
            # adjust estimated worth based on open order
            ord_worth = open_order_values[symbol]
            cur_worth = ava_worth + ord_worth
            bid_worth += ord_worth
            ask_worth += ord_worth

            # determine "step size"
            cur_ratio = cur_worth / folio_worth
            target_worth = ratio * folio_worth
            step = self.params.get(
                "progression_func", self.__class__.DEFAULT_PROGRESSION_FUNC
            )(gap_seconds)
            assert step <= 1.0, f"Step size too large: {step}"

            # calculate tentative market order toward equilibrium
            self._info(
                f"{symbol} worth : tar. {round(target_worth, 2)} ({round(ratio*100, 2)}%) | cur. {round(cur_worth, 2)} ({round(cur_ratio*100, 2)}%)"
            )
            self._info(
                f"{symbol} worth : ava. {round(ava_worth, 2)} | ord. {round(ord_worth, 2)} | bid-ask {round(bid_worth, 2)}-{round(ask_worth, 2)}"
            )
            if target_worth > ask_worth:
                amount = (target_worth - cur_worth) * step
                action = "market buy"
                func = folio.market_buy
            elif item_exists and target_worth < bid_worth:
                amount = (cur_worth - target_worth) * step
                action = "market sell"
                func = folio.market_sell
            else:
                self._info(f"{symbol} near equilibrium, staying put.")

            # make market order
            base_msg = f"{action}: {symbol} | {round(amount, 6)} {folio.cash.name}"
            if execute:
                self._warn(f"attempting {base_msg}")
                info = func(symbol, amount=amount)
                self._warn(f"placed {base_msg}\n{info}")
            else:
                self._info(f"fake {base_msg}")

        for _symbol, _ratio in self.equilibrium.items():
            subroutine(_symbol, _ratio)

        return gap_seconds
