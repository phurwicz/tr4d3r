"""
Mechanism helpers.
"""
from tr4d3r.core import Loggable
from tr4d3r.utils.misc import autostamp
from datetime import datetime


class NamedCallback(Loggable):
    def __init__(self, f, name):
        self._f = f
        self.name = name
        
    def __call__(self, *args, **kwargs):
        return self._f(*args, **kwargs)
    
    def __repr__(self):
        return self.name
    
    
class Tentative(Loggable):
    def __init__(self, condition, trigger, order_time=None, expire_after=86400, verbose=False):
        """
        Trigger a function conditionally at most once with expiration.
        """
        # sanity check
        assert not condition(order_time), f"Condition is not expected to be met immediately"
        
        # initialization
        self.order_time = autostamp(order_time)
        self.expire_time = order_time + expire_after
        self.state_dict = {"expired": False, "triggered": False, "latest": order_time}
        self.condition = condition
        self.trigger = trigger
        self.verbose = bool(verbose)
    
    def __repr__(self):
        status = "expired" if self.state_dict["expired"] else "pending"
        status = "complete" if self.state_dict["triggered"] else "pending"
        read_time = datetime.fromtimestamp(self.state_dict['latest'])
        return f"{self.condition.name} -> {self.trigger.name} | {status} @ {read_time}"
        
    def __call__(self, time):
        """
        Return whether this tentative should be marked as complete.
        """
        # base case: expired or already triggered
        if self.state_dict["expired"] or self.state_dict["triggered"]:
            raise ValueError(f"Calling invalid tentative {self}.")
            #return True
        
        # sanity check: timeline should be consistent
        time = autostamp(time)
        last_time = self.state_dict["latest"]
        assert time >= last_time, f"Illegal limit order state: old time {last_time}, new time {time}"
        
        # exit: order expires
        if time >= self.expire_time:
            self.state_dict["expired"] = True
            self.state_dict["latest"] = time
            if self.verbose:
                self._info(f"{self}")
            return True
        
        # exit: condition is met
        if self.condition(time):
            self.trigger(time)
            self.state_dict["triggered"] = True
            self.state_dict["latest"] = time
            if self.verbose:
                self._info(f"{self}")
            return True
        
        # keep going: order still stands
        self.state_dict["latest"] = time
        return False