# ==============================================================================
# librenogybt-emulator (renogybt-emulator)
# Copyright (c) 2026 Mohammad Hafiz bin Ismail (mypapit@gmail.com) - http://mypapit.net
# Licensed under the GNU General Public License version 3 (GNU/GPL v3).
#
# Inspired by Cyril Sebastian's renogy-bt (https://github.com/cyrils/renogy-bt)
# and designed to work seamlessly with it and other compatible Renogy BLE clients.
# ==============================================================================
"""Standalone unit tests for librenogybt-emulator."""

import os
import pytest
from librenogybt_emulator import (
    RenogyBLEEmulator,
    crc16_modbus,
    derive_alias_from_mac,
    load_emulator_config,
    parse_duration_seconds,
)


def test_derive_alias_and_duration():
    assert derive_alias_from_mac("04:7F:0E:01:E1:E4", hex_digits=6) == "BT-TH-01E1E4"
    assert derive_alias_from_mac("80:6F:B0:66:f9:34:7E", hex_digits=8) == "BT-TH-66f9347E"
    assert parse_duration_seconds("30s") == 30.0
    assert parse_duration_seconds("2m") == 120.0


def test_static_rover_24v_gel_noon_modbus():
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rover_24v_gel_noon.json")
    cfg = load_emulator_config(cfg_path)
    emu = RenogyBLEEmulator(config=cfg, config_path=cfg_path)

    # Read model (register 12, 8 words)
    req_model = bytes([255, 3, 0, 12, 0, 8, 145, 209])
    resp_model = emu.process_write(req_model)
    assert resp_model is not None
    assert resp_model[3:19].decode("utf-8").strip() == "RNG-CTRL-ROVER60"

    # Read charging info (register 256, 34 words)
    req_info = bytes([255, 3, 1, 0, 0, 34, 209, 241])
    resp_info = emu.process_write(req_info)
    assert resp_info is not None
    assert len(resp_info) == 73
    assert int.from_bytes(resp_info[3:5], "big") == 88  # battery_percentage = 88%
    assert int.from_bytes(resp_info[5:7], "big") == 284  # battery_voltage = 28.4V


def test_four_solar_states_cycle():
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rover_24v_gel_states.json")
    cfg = load_emulator_config(cfg_path)
    emu = RenogyBLEEmulator(config=cfg, config_path=cfg_path)
    assert emu.modbus.mode == "cycle"
    assert emu.modbus.states == ["nighttime", "early_morning", "noon", "late_afternoon"]
    assert emu.modbus.current_state == "nighttime"

    for expected_state, expected_soc in [
        ("nighttime", 72),
        ("early_morning", 74),
        ("noon", 88),
        ("late_afternoon", 98),
    ]:
        assert emu.modbus.current_state == expected_state
        resp = emu.process_write(bytes([255, 3, 1, 0, 0, 34, 209, 241]))
        assert int.from_bytes(resp[3:5], "big") == expected_soc
        emu.modbus.advance_state_if_due(force=True)
