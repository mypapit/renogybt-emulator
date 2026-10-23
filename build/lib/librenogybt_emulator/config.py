# ==============================================================================
# librenogybt-emulator (renogybt-emulator)
# Copyright (c) 2026 Mohammad Hafiz bin Ismail (mypapit@gmail.com) - http://mypapit.net
# Licensed under the GNU General Public License version 3 (GNU/GPL v3).
#
# Inspired by Cyril Sebastian's renogy-bt (https://github.com/cyrils/renogy-bt)
# and designed to work seamlessly with it and other compatible Renogy BLE clients.
# ==============================================================================
"""Configuration loader and presets for librenogybt-emulator."""

import configparser
import os
import subprocess
import re
from typing import Dict, Any, Optional

DEFAULT_PRESETS: Dict[str, Dict[str, str]] = {
    "emulator": {
        "adapter": "hci0",
        "mac_addr": "",  # Auto-detected from adapter or defaults to 80:6F:B0:66:F9:34 -> BT-TH-66f9347E
        "alias": "BT-TH-66f9347E",
        "type": "RNG_CTRL",
        "model": "RNG-CTRL-ROVER60",
        "device_id": "97",
        "mode": "static",
        "state_interval": "30s",
        "states": "nighttime, early_morning, noon, late_afternoon",
        "initial_state": "nighttime",
    },
    "rover": {
        "battery_percentage": "87",
        "battery_voltage": "12.9",
        "battery_current": "2.58",
        "battery_temperature": "25",
        "controller_temperature": "33",
        "load_status": "off",
        "load_voltage": "0.0",
        "load_current": "0.0",
        "load_power": "0",
        "pv_voltage": "17.1",
        "pv_current": "2.04",
        "pv_power": "35",
        "max_charging_power_today": "143",
        "max_discharging_power_today": "0",
        "charging_amp_hours_today": "34",
        "discharging_amp_hours_today": "34",
        "power_generation_today": "432",
        "power_consumption_today": "0",
        "power_generation_total": "426038",
        "charging_status": "mppt",
        "battery_type": "lithium",
        "daily_power_generation": "1754, 1907, 1899, 1804, 1841, 1630, 1344",
        "daily_charge_ah": "135, 147, 147, 139, 142, 125, 102",
        "daily_max_power": "234, 344, 360, 335, 331, 307, 290",
    },
    "battery": {
        "model": "RBT100LFP12S-G",
        "device_id": "48",
        "cell_count": "4",
        "cell_voltages": "3.6, 3.6, 3.6, 3.6",
        "sensor_count": "4",
        "temperatures": "21.0, 21.0, 21.0, 21.0",
        "current": "1.4",
        "voltage": "14.5",
        "remaining_charge": "99.941",
        "capacity": "100.0",
    },
    "inverter": {
        "model": "RIV1230RCH-SPS",
        "device_id": "32",
        "input_voltage": "124.9",
        "input_current": "2.2",
        "output_voltage": "124.9",
        "output_current": "1.19",
        "output_frequency": "59.97",
        "battery_voltage": "14.4",
        "temperature": "30.0",
        "input_frequency": "59.97",
        "battery_percentage": "100",
        "charging_current": "0.7",
        "solar_voltage": "0.0",
        "solar_current": "0.0",
        "solar_power": "0",
        "charging_status": "deactivated",
        "charging_power": "10",
        "load_current": "1.2",
        "load_active_power": "108",
        "load_apparent_power": "150",
        "line_charging_current": "0.0",
        "load_percentage": "5",
    },
    "hf_inverter": {
        "model": "RIV1230PCH-23S",
        "device_id": "32",
        "ac_input_voltage": "230.5",
        "ac_input_frequency": "50.0",
        "ac_voltage_setting": "230.0",
        "battery_discharge_current": "15.5",
        "battery_temperature": "25.0",
        "internal_temperature": "35.0",
        "ac_input_present": "1",
        "battery_current": "-12.5",
        "charging_active": "1",
        "charging_power_amps": "12.5",
        "operating_mode": "4",
        "charging_current": "20.0",
        "max_charging_current_setting": "50.0",
    },
    "dc_charger": {
        "model": "RBC50D1S-G1",
        "device_id": "96",
        "battery_percentage": "100",
        "battery_voltage": "13.2",
        "combined_charge_current": "0.0",
        "controller_temperature": "18",
        "battery_temperature": "25",
        "alternator_voltage": "12.9",
        "alternator_current": "0.0",
        "alternator_power": "0",
        "pv_voltage": "0.0",
        "pv_current": "0.0",
        "pv_power": "0",
        "battery_min_voltage_today": "13.2",
        "battery_max_voltage_today": "13.3",
        "battery_max_current_today": "17.02",
        "max_charging_power_today": "238",
        "charging_amp_hours_today": "25",
        "power_generation_today": "336",
        "total_working_days": "703",
        "count_battery_overdischarged": "0",
        "count_battery_fully_charged": "1435",
        "battery_ah_total_accumulated": "5607",
        "power_generation_total": "76580",
        "charging_status": "current limiting",
        "error": "battery_over_discharge",
        "battery_type": "lithium",
    },
    "shunt": {
        "alias": "RTMShunt3001234",
        "main_battery_percent": "100.0",
        "main_battery_voltage": "13.21",
        "starter_battery_voltage": "0.0",
        "charge_amps": "0.02",
        "battery_temperature": "19.9",
    },
    "state:nighttime": {
        "battery_percentage": "72",
        "battery_voltage": "25.0",
        "battery_current": "0.0",
        "battery_temperature": "21",
        "controller_temperature": "23",
        "load_status": "on",
        "load_voltage": "25.0",
        "load_current": "3.6",
        "load_power": "90",
        "pv_voltage": "0.0",
        "pv_current": "0.0",
        "pv_power": "0",
        "max_charging_power_today": "0",
        "max_discharging_power_today": "110",
        "charging_amp_hours_today": "0",
        "discharging_amp_hours_today": "14",
        "power_generation_today": "0",
        "power_consumption_today": "350",
        "power_generation_total": "451120",
        "charging_status": "deactivated",
        "battery_type": "gel",
    },
    "state:early_morning": {
        "battery_percentage": "74",
        "battery_voltage": "26.2",
        "battery_current": "2.4",
        "battery_temperature": "22",
        "controller_temperature": "26",
        "load_status": "on",
        "load_voltage": "26.2",
        "load_current": "1.5",
        "load_power": "39",
        "pv_voltage": "33.8",
        "pv_current": "1.9",
        "pv_power": "64",
        "max_charging_power_today": "75",
        "max_discharging_power_today": "110",
        "charging_amp_hours_today": "4",
        "discharging_amp_hours_today": "16",
        "power_generation_today": "105",
        "power_consumption_today": "410",
        "power_generation_total": "451225",
        "charging_status": "mppt",
        "battery_type": "gel",
    },
    "state:noon": {
        "battery_percentage": "88",
        "battery_voltage": "28.4",
        "battery_current": "18.5",
        "battery_temperature": "28",
        "controller_temperature": "41",
        "load_status": "on",
        "load_voltage": "28.4",
        "load_current": "2.5",
        "load_power": "71",
        "pv_voltage": "42.6",
        "pv_current": "12.8",
        "pv_power": "545",
        "max_charging_power_today": "580",
        "max_discharging_power_today": "110",
        "charging_amp_hours_today": "64",
        "discharging_amp_hours_today": "22",
        "power_generation_today": "1680",
        "power_consumption_today": "560",
        "power_generation_total": "452800",
        "charging_status": "mppt",
        "battery_type": "gel",
    },
    "state:late_afternoon": {
        "battery_percentage": "98",
        "battery_voltage": "27.6",
        "battery_current": "3.2",
        "battery_temperature": "26",
        "controller_temperature": "32",
        "load_status": "on",
        "load_voltage": "27.6",
        "load_current": "2.0",
        "load_power": "55",
        "pv_voltage": "36.4",
        "pv_current": "2.5",
        "pv_power": "91",
        "max_charging_power_today": "580",
        "max_discharging_power_today": "110",
        "charging_amp_hours_today": "92",
        "discharging_amp_hours_today": "28",
        "power_generation_today": "2420",
        "power_consumption_today": "720",
        "power_generation_total": "453540",
        "charging_status": "floating",
        "battery_type": "gel",
    },
}


def detect_adapter_mac(adapter: str = "hci0") -> Optional[str]:
    """Detect the Bluetooth MAC address of the given local adapter if available."""
    sysfs_addr = f"/sys/class/bluetooth/{adapter}/address"
    if os.path.exists(sysfs_addr):
        try:
            with open(sysfs_addr, "r", encoding="utf-8") as f:
                mac = f.read().strip().upper()
                if mac and mac != "00:00:00:00:00:00":
                    return mac
        except OSError:
            pass
    return None


def derive_alias_from_mac(mac_addr: str, prefix: str = "BT-TH-", hex_digits: int = 8) -> str:
    """Derive a BT-TH-<hex> alias from the trailing hex characters of a Bluetooth MAC address."""
    clean_hex = re.sub(r"[^0-9A-Fa-f]", "", mac_addr)
    if len(clean_hex) >= hex_digits:
        return f"{prefix}{clean_hex[-hex_digits:]}"
    if clean_hex:
        return f"{prefix}{clean_hex}"
    return f"{prefix}01E1E4"


def parse_duration_seconds(value: Any, default: float = 30.0) -> float:
    """Parse a duration string in seconds or minutes (e.g. '30', '30s', '2m', '1.5min') into seconds."""
    if value is None:
        return default
    s = str(value).strip().lower()
    if not s:
        return default
    m = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes)?$", s)
    if not m:
        try:
            return float(s)
        except ValueError:
            return default
    num = float(m.group(1))
    unit = m.group(2) or "s"
    if unit.startswith("m"):
        return num * 60.0
    return num


def load_emulator_config(config_path: Optional[str] = None) -> configparser.ConfigParser:
    """Load emulator configuration with presets and optional file override (.ini or .json)."""
    config = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
    config.read_dict(DEFAULT_PRESETS)

    if config_path:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        if config_path.lower().endswith(".json"):
            import json
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                # Support either sectioned dicts, a 'states' dict, or a flat dict of rover/emulator stats
                for k, v in data.items():
                    if k == "states" and isinstance(v, dict):
                        state_names = []
                        for state_name, state_dict in v.items():
                            if isinstance(state_dict, dict):
                                sec_name = f"state:{state_name}"
                                if not config.has_section(sec_name):
                                    config.add_section(sec_name)
                                for sub_k, sub_v in state_dict.items():
                                    config[sec_name][sub_k] = str(sub_v)
                                state_names.append(state_name)
                        if state_names:
                            config["emulator"]["states"] = ", ".join(state_names)
                            if config["emulator"].get("mode", "static") == "static":
                                config["emulator"]["mode"] = "cycle"
                    elif isinstance(v, dict):
                        if not config.has_section(k):
                            config.add_section(k)
                        for sub_k, sub_v in v.items():
                            config[k][sub_k] = str(sub_v)
                    else:
                        if k in config["emulator"]:
                            config["emulator"][k] = str(v)
                        elif k in config["rover"]:
                            config["rover"][k] = str(v)
                        else:
                            config["rover"][k] = str(v)
        else:
            config.read(config_path)

    adapter = config["emulator"].get("adapter", "hci0").strip()
    mac_addr = config["emulator"].get("mac_addr", "").strip()
    if not mac_addr:
        detected = detect_adapter_mac(adapter)
        mac_addr = detected if detected else "80:6F:B0:66:F9:34"
        config["emulator"]["mac_addr"] = mac_addr

    alias = config["emulator"].get("alias", "").strip()
    if not alias or alias.lower() in ("auto", "auto6", "auto8"):
        digits = 6 if alias.lower() in ("auto", "auto6") else 8
        config["emulator"]["alias"] = derive_alias_from_mac(mac_addr, hex_digits=digits)

    return config
