"""Lock to prevent sending multiple command at once to Epson projector."""

import time
from .const import (TURN_ON, TURN_OFF, INV_SOURCES, SOURCE, ALL, TIMEOUT_TIMES)


class Lock:
    def __init__(self):
        """Init lock for sending request to projector when it is busy."""
        self._isLocked = False
        self._timer = 0
        self._operation = False

    def setLock(self, command):
        """Set lock on requests."""
        if command in (TURN_ON, TURN_OFF):
            self._operation = command
        elif command in INV_SOURCES:
            self._operation = SOURCE
        else:
            self._operation = ALL
        self._isLocked = True
        self._timer = time.time()

    def __unlock(self):
        """Unlock sending requests to projector."""
        self._operation = False
        self._timer = 0
        self._isLocked = False

    def checkLock(self):
        """
        Lock checking.

        Check if there is lock pending and check if enough time
        passed so requests can be unlocked.
        """
        if self._isLocked:
            if (time.time() - self._timer) > TIMEOUT_TIMES[self._operation]:
                self.__unlock()
                return False
            return True
        return False
