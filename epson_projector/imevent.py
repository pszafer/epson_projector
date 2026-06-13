"""This module defines the IMEVENT message and related enums."""

from __future__ import annotations

from enum import IntEnum, IntFlag
import logging

_LOGGER = logging.getLogger(__name__)


class ProjectorStatus(IntEnum):
    STANDBY = 0x01
    WARMUP = 0x02
    NORMAL = 0x03
    COOLDOWN = 0x04
    ABNORMAL = 0xFF

    _UNKNOWN = -1

    @classmethod
    def _missing_(cls, value: object) -> ProjectorStatus:
        _LOGGER.warning("Unknown value '%s' for %s", value, cls.__name__)
        return cls._UNKNOWN


class WarningType(IntFlag):
    LAMP_LIFE = 0x01
    NO_SIGNAL = 0x02
    UNSUPPORTED_SIGNAL = 0x04
    AIR_FILTER = 0x08
    HIGH_TEMPERATURE = 0x10
    ASPECT_CHANGE = 0x40


class AlarmType(IntFlag):
    LAMP_ON_FAILURE = 0x01
    LAMP_LID = 0x02
    LAMP_BURNOUT = 0x04
    FAN = 0x08
    TEMPERATURE_SENSOR = 0x10
    HIGH_TEMPERATURE = 0x20
    INTERIOR_SYSTEM = 0x40


class ImEvent:
    def __init__(
        self,
        event_code: int,
        power_status: ProjectorStatus,
        warning_type: WarningType,
        alarm_type: AlarmType,
    ):
        self.event_code = event_code
        self.power_status = power_status
        self.warning_type = warning_type
        self.alarm_type = alarm_type

    def __str__(self) -> str:
        return f"ImEvent(event_code={self.event_code}, power_status={self.power_status}, warning_type={self.warning_type.name}, alarm_type={self.alarm_type.name})"

    @staticmethod
    def from_message(raw_message: bytes) -> ImEvent:
        """Parse an IMEVENT message and return an ImEvent object."""

        # Example message from LS11000
        # b'IMEVENT=0001 03 00000002 00000000 T1 F1\r:'
        message = raw_message.decode().rstrip("\r:")

        (command, value) = message.split(sep="=", maxsplit=1)
        if command != "IMEVENT":
            raise ValueError(f"Command {command} is not IMEVENT")

        parts = value.split()
        if len(parts) < 4:
            raise ValueError(
                f"Expected at least eventcode and 3 parameters. Found {len(parts)} in message: {message}"
            )

        event_code = int(parts[0], 16)
        if event_code != 1:
            raise ValueError(f"Unknown event code: {event_code}")

        # Decode parameters
        power_status = ProjectorStatus(int(parts[1], 16))
        warning_type = WarningType(int(parts[2], 16))
        alarm_type = AlarmType(int(parts[3], 16))

        # Any postfixes like T1 and F1 are discarded because the meaning is unknown.

        return ImEvent(
            event_code=event_code,
            power_status=power_status,
            warning_type=warning_type,
            alarm_type=alarm_type,
        )
