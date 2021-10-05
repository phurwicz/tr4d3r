"""
Random-number utility functions.
"""
import numpy as np


def exponential_random_walk(rng, initial, steps, **kwargs):
    """
    An expontential random walk from a scalar or vector of initial values.
    """
    # determine dimensionality based on initial values and number of steps
    shape_initial = np.asarray(initial).shape
    assert len(shape_initial) <= 1, f"Expected scalar or 1-D array, got {initial}"
    shape_steps = (steps, *shape_initial)
    
    # sample individual steps and cumsum for random walk
    log_initial = np.log(initial)
    log_initial_broadcast = log_initial[np.newaxis] if len(shape_initial) == 0 else log_initial[np.newaxis, :]
    log_increments = rng.normal(size=shape_steps, **kwargs)
    log_walk = np.concatenate(
        (log_initial_broadcast, log_increments),
        axis=0,
    ).cumsum(axis=0)
    final_walk = np.exp(log_walk)
    return final_walk
