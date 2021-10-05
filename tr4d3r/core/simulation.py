"""
Simulation classes.
"""
from tr4d3r.core import Loggable
from tqdm import tqdm
import pandas as pd


class Simulation(Loggable):
    """
    Simulation with pseuto-time objects.
    """
    def __init__(self, market_cls, *args, **kwargs):
        self.init_kwargs = kwargs
        self.market = market_cls(*args, **kwargs)
        
    def run(self, manager, folio, time_sequence, timed_callbacks=None):
        """
        TODO: cache sequences and load when a new sequence is a contiguous subset with the same start.
        """
        timed_callbacks = timed_callbacks or {}
        
        data_entries = []
        for _time in tqdm(time_sequence, desc="Simulation step"):
            # find any callback and trigger it
            if _time in timed_callbacks.keys():
                _callback = timed_callbacks[_time]
                _callback(_time)
            # regular read/write subroutine
            data_entries.append(manager.tick_read(folio, _time))
            manager.tick_write(folio, _time)
        
        df = pd.DataFrame(data_entries)
        info = {
            'portfolio': folio,
            'market': self.market,
            'df': df,
        }
        return info