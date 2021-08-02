from .const import TIMEOUT_TIMES, DEFAULT_TIMEOUT_TIME

def get_timeout(command, timeout_scale=1):
    return TIMEOUT_TIMES.get(command, DEFAULT_TIMEOUT_TIME) * timeout_scale
