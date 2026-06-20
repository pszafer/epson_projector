from __future__ import annotations

import pytest

from epson_projector.imevent import AlarmType, ImEvent, ProjectorStatus, WarningType


@pytest.mark.parametrize(
    ("raw_message", "power_status", "warning_type", "alarm_type"),
    [
        (
            # Message captured from LS11000
            b"IMEVENT=0001 03 00000002 00000000 T1 F1\r:",
            ProjectorStatus.NORMAL,
            WarningType.NO_SIGNAL,
            AlarmType(0),
        ),
        (
            # Message from ESC/VP.net documentation
            b"IMEVENT=0001 01 0001 0001",
            ProjectorStatus.STANDBY,
            WarningType.LAMP_LIFE,
            AlarmType.LAMP_ON_FAILURE,
        ),
    ],
)
def test_from_message_parses_known_imevent_formats(
    raw_message: bytes,
    power_status: ProjectorStatus,
    warning_type: WarningType,
    alarm_type: AlarmType,
):
    event = ImEvent.from_message(raw_message)

    assert event.event_code == 1
    assert event.power_status == power_status
    assert event.warning_type == warning_type
    assert event.alarm_type == alarm_type
