# ==============================================================================
# librenogybt-emulator (renogybt-emulator)
# Copyright (c) 2026 Mohammad Hafiz bin Ismail (mypapit@gmail.com) - http://mypapit.net
# Licensed under the GNU General Public License version 3 (GNU/GPL v3).
#
# Inspired by Cyril Sebastian's renogy-bt (https://github.com/cyrils/renogy-bt)
# and designed to work seamlessly with it and other compatible Renogy BLE clients.
# ==============================================================================
"""librenogybt-emulator: Emulate Renogy BT-1 / BT-2 BLE modules and Modbus RTU registers."""

from .config import (
    DEFAULT_PRESETS,
    derive_alias_from_mac,
    detect_adapter_mac,
    load_emulator_config,
    parse_duration_seconds,
)
from .modbus import RenogyModbusDevice, crc16_modbus, encode_temperature_byte
from .server import (
    NOTIFY_CHAR_UUID,
    NOTIFY_SERVICE_UUID,
    SHUNT_NOTIFY_CHAR_UUID,
    SHUNT_SERVICE_UUID,
    WRITE_CHAR_UUID,
    WRITE_SERVICE_UUID,
    RenogyBLEEmulator,
)

__all__ = [
    "DEFAULT_PRESETS",
    "derive_alias_from_mac",
    "detect_adapter_mac",
    "load_emulator_config",
    "RenogyModbusDevice",
    "crc16_modbus",
    "encode_temperature_byte",
    "RenogyBLEEmulator",
    "WRITE_SERVICE_UUID",
    "WRITE_CHAR_UUID",
    "NOTIFY_SERVICE_UUID",
    "NOTIFY_CHAR_UUID",
    "SHUNT_SERVICE_UUID",
    "SHUNT_NOTIFY_CHAR_UUID",
]
