import wrappy
import robin_stocks.robinhood as rh
from tr4d3r.core.asset import Cash
from tr4d3r.core.portfolio import RealTimePortfolio
from .asset import RobinhoodRealItem
from .market import RobinhoodRealMarket
from .utils import cached_order_info
from collections import defaultdict
from pprint import pformat


class RobinhoodRealPortfolio(RealTimePortfolio):
    """
    A real portfolio on Robinhood.
    """
    
    DEFAULT_CASH_CLASS = Cash
    CASH_NAME = 'USD'
    DEFAULT_ITEM_CLASS = RobinhoodRealItem
    DUMMY_ITEM = RobinhoodRealItem('Robinhood-N/A', quantity=0.0, unit_cost=0.0)
    
    def __init__(self, principal, cash, items, open_orders, **kwargs):
        """
        Log -> Load -> Check -> Construct.
        """
        #self._info("Logging in to Robinhood..")
        #rh.login()
        
        # constructor
        self._info("Constructing portfolio..")
        super().__init__(principal, cash, items, open_orders, **kwargs)
        self.market = RobinhoodRealMarket()
       
        # resolve filled orders, consistency check
        # get information from Robinhood
        self._info("Checking online info..")
        self.refresh_open_orders()
        self.validate_cash()
        self.validate_items()
        self._good(f"Checks passed.\n{pformat(self.to_dict())}")
        
    @classmethod
    def order_brief(cls, order_dict, detail_level=0):
        """
        Get the most critical information of an order.
        """
        if order_dict is None:
            return dict(info='No transaction')
        
        assert isinstance(detail_level, int)
        symbol = rh.get_instrument_by_url(order_dict['instrument'], info='symbol')
        amount = float(order_dict['total_notional']['amount'])
        brief = dict(symbol=symbol)        
        brief.update({_k: order_dict.get(_k, None) for _k in ['type', 'side', 'state', 'price', 'quantity']})
        brief.update(dict(amount=amount))
        if detail_level >= 1:
            brief.update({_k: order_dict.get(_k, None) for _k in ['id', 'created_at']})
        return brief
    
    @classmethod
    def order_side_to_bool(cls, side):
        if side == 'buy':
            return True
        elif side == 'sell':
            return False
        else:
            raise ValueError(f"Expected buy or sell, got {side}")
        
    def open_order_values(self):
        value_dict = defaultdict(float)
        for _order_id in self.open_orders:
            _order_dict = cached_order_info(_order_id)
            _symbol, _side, _amount = _order_dict['symbol'], _order_dict['side'], float(_order_dict['total_notional']['amount'])
            
            _buy_flag = self.__class__.order_side_to_bool(_side)
            _coeff = 1 if _buy_flag else -1
            value_dict[_symbol] += _coeff * _amount
        return value_dict
            
    def resolve_filled_order(self, order):
        """
        Expected to be executed exactly once for each order.
        """
        side = order['side']
        symbol = order['symbol']
        buy_flag = self.__class__.order_side_to_bool(side)
        
        assert len(order['executions']) == 1, f"Expected exactly one execution, got {order['executions']}"
        unit_cost = float(order['executions'][0]['price'])
        quantity = float(order['executions'][0]['quantity'])
        amount = float(order['executed_notional']['amount'])
        currency = order['executed_notional']['currency_code']
        cash = self.__class__.DEFAULT_CASH_CLASS(currency, amount)
        item = self.__class__.DEFAULT_ITEM_CLASS(symbol, quantity, unit_cost)
        
        if buy_flag:
            self.cash.sub(cash)
            self.add_item(item)
        else:
            self.sub_item(item)
            self.cash.add(cash)
            self.check(item.name)
            
    def refresh_single_open_order(self, order_id):
        """
        Refresh the state of an open order.
        If it is now filled, resolve its transaction and close it.
        If it has failed / been cancelled, make an alert.
        """
        order = rh.get_stock_order_info(order_id)
        assert order['type'] == 'market', f"Expected a market order, got {order['type']}"
            
        brief = self.__class__.order_brief(order)
        order['symbol'] = brief['symbol']
        
        state = order['state']
        if state in {'unconfirmed', 'confirmed', 'queued'}:
            # stay in the open order list
            self._info(f"Order pending: {brief}")
        elif state == 'filled':
            # read quantity/amount and change cash/item
            self._good(f"Order complete: {brief}")
            self.open_orders.remove(order_id)
            self.resolve_filled_order(order)
        elif state in {'failed', 'canceled'}:
            self._fail(f"Order failed: {brief}")
            self.open_orders.remove(order_id)
        else:
            raise ValueError(f"Unexpected state {state} for order id {order_id}")
        
    def refresh_open_orders(self):
        """
        Refresh the state of all open orders.
        """
        open_order_ids = self.open_orders.copy()
        for _order_id in open_order_ids:
            self.refresh_single_open_order(_order_id)
    
    def validate_cash(self):
        """
        Subroutine of the constructor. Validate local cash against online cash.
        """
        cash = self.cash
        available_cash = float(rh.load_account_profile('cash'))
        assert cash.name == self.__class__.CASH_NAME, f"Unexpected cash name: {cash.name}"
        assert cash.quantity <= available_cash, f"Expected cash >= {cash.quantity}, got {available_cash}"
        
    def validate_items(self):
        """
        Subroutine of the constructor. Validate local items against online holdings.
        """
        holdings_dict = rh.build_holdings()
        for _item in self.item_dict.values():
            assert _item.name in holdings_dict, f"Expected item {_symbol} in holdings"
            _online_dict = holdings_dict[_item.name]
            
            _offline_q = _item.quantity
            _online_q = float(_online_dict["quantity"])
            assert _offline_q == _online_q, f"Expected {_item.name} quantity {_offline_q}, got {_online_q}"
            
            _offline_c = _item.unit_cost
            _online_c = float(_online_dict["average_buy_price"])
            assert _offline_q == _online_q, f"Expected {_item.name} unit cost {_offline_c}, got {_online_c}"
    
    def market_buy(self, *args, **kwargs):
        """
        Customizing over parent method: keep a brief version of info.
        """
        order = super().market_buy(*args, **kwargs)
        return self.__class__.order_brief(order)
    
    def market_sell(self, *args, **kwargs):
        """
        Customizing over parent method: keep a brief version of info.
        """
        order = super().market_sell(*args, **kwargs)
        return self.__class__.order_brief(order)
    
    def local_deposit(self, amount):
        """
        Put more cash under this particular portfolio.
        """
        if amount == 0:
            self._warn("Trivial deposit amount")
            return
        assert amount > 0, "Invalid deposit amount: {amount}"
        # make sure there is enough cash
        target = self.cash.quantity + amount
        available_cash = float(rh.load_account_profile('cash'))
        assert target <= available_cash, f"Expected cash >= {target}, got {available_cash}"
        self.principal.quantity += amount
        self.cash.quantity = target
        
        return
    
    def local_withdraw(self, amount):
        """
        Pull cash from this particular portfolio.
        """
        if amount == 0:
            self._warn("Trivial withdrawal amount")
            return
        assert amount > 0, "Invalid withdrawal amount: {amount}"
        assert self.cash.quantity >= amount, f"Not enough cash ({self.cash.quantity}) to withdraw ({amount})"
        self.principal.quantity -= amount
        self.cash.quantity -= amount
        
        return