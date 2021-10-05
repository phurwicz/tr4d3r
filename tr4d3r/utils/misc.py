from datetime import datetime, timedelta, timezone
from functools import lru_cache, wraps

DATETIME_FORMAT = "%Y%m%d %H:%M:%S.%f %z"

def utcnow():
    return datetime.now().astimezone(timezone.utc)

def datetime_to_string(dt):
    assert isinstance(dt, datetime), f"Expected datetime, got {type(dt)} {dt}"
    dt_utc = dt.astimezone(timezone.utc)
    dt_str = dt_utc.strftime(DATETIME_FORMAT)
    return dt_str

def string_to_datetime(dt_str):
    assert isinstance(dt_str, str), f"Expected string, got {type(dt_str)} {dt_str}"
    dt = datetime.strptime(dt_str, DATETIME_FORMAT)
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc
    
def autostamp(time):
    time = time or utcnow()
    if isinstance(time, datetime):
        time = time.timestamp()
    assert isinstance(time, float), f"Expected float, got {type(time)} {time}"
    return time

def autodatetime(dt):
    dt = dt or utcnow()
    if isinstance(dt, float):
        dt = datetime.fromtimestamp(dt).astimezone(timezone.utc)
    assert isinstance(dt, datetime), f"Expected datetime, got {type(dt)} {dt}"
    return dt
    
def timed_lru_cache(seconds: int, maxsize: int = 128):
    def wrapper_cache(func):
        func = lru_cache(maxsize=maxsize)(func)
        func.lifetime = timedelta(seconds=seconds)
        func.expiration = utcnow() + func.lifetime

        @wraps(func)
        def wrapped_func(*args, **kwargs):
            current_time = utcnow()
            if current_time >= func.expiration:
                func.cache_clear()
                func.expiration = current_time + func.lifetime

            return func(*args, **kwargs)

        return wrapped_func

    return wrapper_cache