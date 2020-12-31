from .const import TIMEOUT_TIMES

def get_timeout(self, command=None, timeout_scale=1):
        if command in TIMEOUT_TIMES:
            return TIMEOUT_TIMES[command] * timeout_scale
        else:
            return TIMEOUT_TIMES['ALL'] * timeout_scale