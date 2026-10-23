# ==============================================================================
# librenogybt-emulator (renogybt-emulator)
# Copyright (c) 2026 Mohammad Hafiz bin Ismail (mypapit@gmail.com) - http://mypapit.net
# Licensed under the GNU General Public License version 3 (GNU/GPL v3).
#
# Inspired by Cyril Sebastian's renogy-bt (https://github.com/cyrils/renogy-bt)
# and designed to work seamlessly with it and other compatible Renogy BLE clients.
# ==============================================================================
"""Modbus RTU and Shunt packet emulator for Renogy BT-1 / BT-2 devices."""

import configparser
import logging
import os
import time
from typing import Dict, List, Optional, Tuple

from .config import parse_duration_seconds

logger = logging.getLogger(__name__)

CRC16_LOW_BYTES = (
    0x00, 0xC0, 0xC1, 0x01, 0xC3, 0x03, 0x02, 0xC2, 0xC6, 0x06, 0x07, 0xC7, 0x05, 0xC5, 0xC4, 0x04,
    0xCC, 0x0C, 0x0D, 0xCD, 0x0F, 0xCF, 0xCE, 0x0E, 0x0A, 0xCA, 0xCB, 0x0B, 0xC9, 0x09, 0x08, 0xC8,
    0xD8, 0x18, 0x19, 0xD9, 0x1B, 0xDB, 0xDA, 0x1A, 0x1E, 0xDE, 0xDF, 0x1F, 0xDD, 0x1D, 0x1C, 0xDC,
    0x14, 0xD4, 0xD5, 0x15, 0xD7, 0x17, 0x16, 0xD6, 0xD2, 0x12, 0x13, 0xD3, 0x11, 0xD1, 0xD0, 0x10,
    0xF0, 0x30, 0x31, 0xF1, 0x33, 0xF3, 0xF2, 0x32, 0x36, 0xF6, 0xF7, 0x37, 0xF5, 0x35, 0x34, 0xF4,
    0x3C, 0xFC, 0xFD, 0x3D, 0xFF, 0x3F, 0x3E, 0xFE, 0xFA, 0x3A, 0x3B, 0xFB, 0x39, 0xF9, 0xF8, 0x38,
    0x28, 0xE8, 0xE9, 0x29, 0xEB, 0x2B, 0x2A, 0xEA, 0xEE, 0x2E, 0x2F, 0xEF, 0x2D, 0xED, 0xEC, 0x2C,
    0xE4, 0x24, 0x25, 0xE5, 0x27, 0xE7, 0xE6, 0x26, 0x22, 0xE2, 0xE3, 0x23, 0xE1, 0x21, 0x20, 0xE0,
    0xA0, 0x60, 0x61, 0xA1, 0x63, 0xA3, 0xA2, 0x62, 0x66, 0xA6, 0xA7, 0x67, 0xA5, 0x65, 0x64, 0xA4,
    0x6C, 0xAC, 0xAD, 0x6D, 0xAF, 0x6F, 0x6E, 0xAE, 0xAA, 0x6A, 0x6B, 0xAB, 0x69, 0xA9, 0xA8, 0x68,
    0x78, 0xB8, 0xB9, 0x79, 0xBB, 0x7B, 0x7A, 0xBA, 0xBE, 0x7E, 0x7F, 0xBF, 0x7D, 0xBD, 0xBC, 0x7C,
    0xB4, 0x74, 0x75, 0xB5, 0x77, 0xB7, 0xB6, 0x76, 0x72, 0xB2, 0xB3, 0x73, 0xB1, 0x71, 0x70, 0xB0,
    0x50, 0x90, 0x91, 0x51, 0x93, 0x53, 0x52, 0x92, 0x96, 0x56, 0x57, 0x97, 0x55, 0x95, 0x94, 0x54,
    0x9C, 0x5C, 0x5D, 0x9D, 0x5F, 0x9F, 0x9E, 0x5E, 0x5A, 0x9A, 0x9B, 0x5B, 0x99, 0x59, 0x58, 0x98,
    0x88, 0x48, 0x49, 0x89, 0x4B, 0x8B, 0x8A, 0x4A, 0x4E, 0x8E, 0x8F, 0x4F, 0x8D, 0x4D, 0x4C, 0x8C,
    0x44, 0x84, 0x85, 0x45, 0x87, 0x47, 0x46, 0x86, 0x82, 0x42, 0x43, 0x83, 0x41, 0x81, 0x80, 0x40
)

CRC16_HIGH_BYTES = (
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40
)


def crc16_modbus(data: bytes) -> bytes:
    """Calculate CRC-16 for Modbus (matches renogybt.Utils.crc16_modbus)."""
    crc_high = 0xFF
    crc_low = 0xFF
    for byte in data:
        index = crc_high ^ int(byte)
        crc_high = crc_low ^ CRC16_HIGH_BYTES[index]
        crc_low = CRC16_LOW_BYTES[index]
    return bytes([crc_high, crc_low])


def encode_temperature_byte(celsius: int) -> int:
    """Encode signed temperature in Celsius to 1-byte sign-magnitude used by Renogy controllers."""
    if celsius < 0:
        return (abs(int(celsius)) & 0x7F) | 0x80
    return int(celsius) & 0x7F


ROVER_CHARGING_STATE_REVERSE = {
    "deactivated": 0,
    "activated": 1,
    "mppt": 2,
    "equalizing": 3,
    "boost": 4,
    "floating": 5,
    "current limiting": 6,
    "alternator direct": 8,
}

INVERTER_CHARGING_STATE_REVERSE = {
    "deactivated": 0,
    "constant current": 1,
    "constant voltage": 2,
    "floating": 4,
    "battery activation": 6,
    "battery disconnecting": 7,
}

BATTERY_TYPE_REVERSE = {
    "open": 1,
    "sealed": 2,
    "gel": 3,
    "lithium": 4,
    "custom": 5,
}


class RenogyModbusDevice:
    """Emulates the register bank and Modbus RTU / notification payloads for Renogy devices."""

    def __init__(self, config: configparser.ConfigParser, config_path: Optional[str] = None):
        self.config = config
        self.config_path = config_path
        self._last_mtime: float = os.path.getmtime(config_path) if config_path and os.path.exists(config_path) else 0.0
        self.device_type = config["emulator"].get("type", "RNG_CTRL").strip()
        self.device_id = config["emulator"].getint("device_id", fallback=97)
        self.load_status = 1 if config["rover"].get("load_status", "off").strip().lower() in ("on", "1", "true") else 0

        self.mode: str = "static"
        self.states: List[str] = []
        self.state_interval_sec: float = 30.0
        self.current_state_index: int = 0
        self._last_state_switch: float = time.monotonic()
        self._init_state_cycle()

    def _init_state_cycle(self):
        """Initialize or refresh multi-state MPPT cycling parameters from config."""
        emu = self.config["emulator"]
        self.mode = emu.get("mode", "static").strip().lower()
        self.state_interval_sec = parse_duration_seconds(emu.get("state_interval", "30s"), default=30.0)
        raw_states = [s.strip() for s in emu.get("states", "").split(",") if s.strip()]
        valid_states = []
        for s in raw_states:
            if self.config.has_section(f"state:{s}") or self.config.has_section(s):
                valid_states.append(s)
        self.states = valid_states
        if self.mode == "cycle" and self.states:
            initial = emu.get("initial_state", "").strip()
            if initial in self.states:
                self.current_state_index = self.states.index(initial)
            elif self.current_state_index >= len(self.states):
                self.current_state_index = 0
            self.apply_state(self.states[self.current_state_index])
            self._last_state_switch = time.monotonic()

    @property
    def current_state(self) -> Optional[str]:
        if self.mode == "cycle" and self.states:
            return self.states[self.current_state_index % len(self.states)]
        return None

    def apply_state(self, state_name: str) -> bool:
        """Apply a named solar MPPT state section (e.g. [state:noon]) into the active [rover] registers."""
        sec_name = f"state:{state_name}" if self.config.has_section(f"state:{state_name}") else (
            state_name if self.config.has_section(state_name) else None
        )
        if not sec_name:
            logger.warning("State section '%s' not found in configuration", state_name)
            return False
        for k, v in self.config[sec_name].items():
            self.config["rover"][k] = str(v)
        self.load_status = 1 if self.config["rover"].get("load_status", "off").strip().lower() in ("on", "1", "true") else 0
        logger.info(
            "Solar MPPT state active: '%s' [charging_status=%s, pv_power=%sW, batt_v=%sV, batt_c=%sA, soc=%s%%]",
            state_name,
            self.config["rover"].get("charging_status"),
            self.config["rover"].get("pv_power"),
            self.config["rover"].get("battery_voltage"),
            self.config["rover"].get("battery_current"),
            self.config["rover"].get("battery_percentage"),
        )
        return True

    def advance_state_if_due(self, force: bool = False) -> Optional[str]:
        """Advance to the next solar MPPT state if state_interval_sec has elapsed (or if forced)."""
        if self.mode != "cycle" or not self.states:
            return None
        now = time.monotonic()
        if force or (self.state_interval_sec > 0 and (now - self._last_state_switch) >= self.state_interval_sec):
            self.current_state_index = (self.current_state_index + 1) % len(self.states)
            self._last_state_switch = now
            state_name = self.states[self.current_state_index]
            self.apply_state(state_name)
            return state_name
        return None

    def reload_config_if_needed(self):
        """Reload configuration file on the fly if it was modified on disk, and check state timer."""
        if self.config_path and os.path.exists(self.config_path):
            try:
                from .config import load_emulator_config
                mtime = os.path.getmtime(self.config_path)
                if mtime > self._last_mtime:
                    self._last_mtime = mtime
                    new_cfg = load_emulator_config(self.config_path)
                    # Preserve runtime CLI overrides if any
                    for k in ("mode", "state_interval", "initial_state"):
                        if k in self.config["emulator"] and k not in new_cfg["emulator"]:
                            new_cfg["emulator"][k] = self.config["emulator"][k]
                    self.config = new_cfg
                    self.device_type = self.config["emulator"].get("type", "RNG_CTRL").strip()
                    self.load_status = 1 if self.config["rover"].get("load_status", "off").strip().lower() in ("on", "1", "true") else 0
                    self._init_state_cycle()
            except Exception as e:
                logger.debug("Config reload skipped: %s", e)
        self.advance_state_if_due()

    def handle_request(self, request: bytes) -> Optional[bytearray]:
        """Process an incoming 8-byte Modbus RTU request frame and return the response frame."""
        self.reload_config_if_needed()
        if len(request) < 8:
            logger.warning("Request too short (%d bytes): %s", len(request), request.hex())
            return None

        req_dev_id = request[0]
        function = request[1]
        reg_addr = int.from_bytes(request[2:4], byteorder="big")
        word_count_or_val = int.from_bytes(request[4:6], byteorder="big")
        req_crc = request[6:8]
        calc_crc = crc16_modbus(request[:6])

        if req_crc != calc_crc:
            logger.warning("CRC mismatch: got %s, expected %s", req_crc.hex(), calc_crc.hex())

        # Respond to broadcast 255 or matching device_id (or any ID if configured)
        if function == 6:  # Write single register (e.g. Rover set_load on register 266, or set device_id on 26)
            if reg_addr == 266:
                self.load_status = 1 if word_count_or_val else 0
                self.config["rover"]["load_status"] = "on" if self.load_status else "off"
            elif reg_addr == 26:
                self.device_id = word_count_or_val & 0xFF
                self.config["emulator"]["device_id"] = str(self.device_id)
            # Echo back the write request with valid CRC
            resp_body = bytes([req_dev_id, 6]) + request[2:6]
            return bytearray(resp_body + crc16_modbus(resp_body))

        if function == 3:  # Read holding registers
            payload_bytes = self._build_read_payload(reg_addr, word_count_or_val)
            if payload_bytes is None:
                # Return Modbus exception response (0x83 = 131)
                err_body = bytes([req_dev_id, 131, 2])
                return bytearray(err_body + crc16_modbus(err_body))

            expected_byte_len = word_count_or_val * 2
            if len(payload_bytes) != expected_byte_len:
                # Pad or truncate to exact word_count * 2
                if len(payload_bytes) < expected_byte_len:
                    payload_bytes = payload_bytes + bytearray(expected_byte_len - len(payload_bytes))
                else:
                    payload_bytes = payload_bytes[:expected_byte_len]

            # Note: For DCChargerClient register 288, byte 2 is used for charging_status!
            header = bytearray([req_dev_id, 3, expected_byte_len])
            if self.device_type == "RNG_DCC" and reg_addr == 288 and word_count_or_val == 3:
                charging_str = self.config["dc_charger"].get("charging_status", "current limiting").strip().lower()
                header[2] = ROVER_CHARGING_STATE_REVERSE.get(charging_str, 6)

            full_body = bytes(header) + bytes(payload_bytes)
            crc = crc16_modbus(full_body)
            return bytearray(full_body + crc)

        logger.warning("Unsupported Modbus function code: %d", function)
        return None

    def _build_rover_register_map(self) -> Dict[int, int]:
        """Build a complete 16-bit word map for Rover registers so arbitrary start/count slices succeed."""
        sec = self.config["rover"]
        regs: Dict[int, int] = {}

        # System Info (0x000A .. 0x0027)
        regs[10] = (24 << 8) | 60  # Max system voltage 24V, rated charging current 60A
        regs[11] = (20 << 8) | 0   # Rated discharging current 20A, product type 0 (controller)

        # Model (0x000C .. 0x0013 = regs 12..19, 8 words = 16 ASCII bytes)
        if self.device_type == "RNG_DCC":
            model = self.config["dc_charger"].get("model", "RBC50D1S-G1")
        else:
            model = self.config["emulator"].get("model", "RNG-CTRL-ROVER60")
        model_bytes = model.encode("utf-8")[:16].ljust(16, b" ")
        for i in range(8):
            regs[12 + i] = int.from_bytes(model_bytes[i * 2 : i * 2 + 2], "big")

        # Software version (0x0014..0x0015 = 20..21), Hardware version (0x0016..0x0017 = 22..23), Serial (0x0018..0x0019 = 24..25)
        regs[20] = 0x0001
        regs[21] = 0x0000
        regs[22] = 0x0001
        regs[23] = 0x0000
        regs[24] = 0x1501
        regs[25] = 0x0064

        # Device ID (0x001A = 26)
        dev_id = (
            self.config["dc_charger"].getint("device_id", self.device_id)
            if self.device_type == "RNG_DCC"
            else self.device_id
        )
        regs[26] = dev_id

        # Extra system registers (27..39)
        for r in range(27, 40):
            regs[r] = 0

        # Dynamic Controller Data (0x0100 .. 0x0122 = regs 256..290)
        batt_pct = int(float(sec.get("battery_percentage", "87")))
        batt_v = int(round(float(sec.get("battery_voltage", "12.9")) * 10))
        batt_c = int(round(float(sec.get("battery_current", "2.58")) * 100))
        ctrl_temp = encode_temperature_byte(int(float(sec.get("controller_temperature", "33"))))
        batt_temp = encode_temperature_byte(int(float(sec.get("battery_temperature", "25"))))
        load_v = int(round(float(sec.get("load_voltage", "0.0")) * 10))
        load_c = int(round(float(sec.get("load_current", "0.0")) * 100))
        load_p = int(float(sec.get("load_power", "0")))
        pv_v = int(round(float(sec.get("pv_voltage", "17.1")) * 10))
        pv_c = int(round(float(sec.get("pv_current", "2.04")) * 100))
        pv_p = int(float(sec.get("pv_power", "35")))
        max_chg_p = int(float(sec.get("max_charging_power_today", "143")))
        max_dis_p = int(float(sec.get("max_discharging_power_today", "0")))
        chg_ah = int(float(sec.get("charging_amp_hours_today", "34")))
        dis_ah = int(float(sec.get("discharging_amp_hours_today", "34")))
        gen_today = int(float(sec.get("power_generation_today", "432")))
        con_today = int(float(sec.get("power_consumption_today", "0")))
        gen_total = int(float(sec.get("power_generation_total", "426038")))
        load_on = 1 if sec.get("load_status", "off").strip().lower() in ("on", "1", "true") else self.load_status
        chg_state = ROVER_CHARGING_STATE_REVERSE.get(sec.get("charging_status", "mppt").strip().lower(), 2)

        regs[256] = batt_pct
        regs[257] = batt_v
        regs[258] = batt_c
        regs[259] = (ctrl_temp << 8) | batt_temp
        regs[260] = load_v
        regs[261] = load_c
        regs[262] = load_p
        regs[263] = pv_v
        regs[264] = pv_c
        regs[265] = pv_p
        regs[266] = load_on
        regs[267] = int(round((batt_v - 5))) if batt_v > 5 else batt_v  # min battery voltage today
        regs[268] = batt_v  # max battery voltage today
        regs[269] = batt_c  # max charging current today
        regs[270] = load_c  # max discharging current today
        regs[271] = max_chg_p
        regs[272] = max_dis_p
        regs[273] = chg_ah
        regs[274] = dis_ah
        regs[275] = gen_today
        regs[276] = con_today
        regs[277] = 365  # total operating days
        regs[278] = 0    # total battery over-discharges
        regs[279] = 120  # total battery full-charges
        # Total charging Ah (280..281), Total discharging Ah (282..283)
        total_ah = max(chg_ah * 100, 1000)
        regs[280] = (total_ah >> 16) & 0xFFFF
        regs[281] = total_ah & 0xFFFF
        regs[282] = 0
        regs[283] = 500
        # Cumulative power generation (284..285)
        regs[284] = (gen_total >> 16) & 0xFFFF
        regs[285] = gen_total & 0xFFFF
        # Cumulative power consumption (286..287)
        regs[286] = 0
        regs[287] = con_today * 10
        # Street light status + brightness & charging state (288)
        regs[288] = (((load_on & 1) << 7) << 8) | (chg_state & 0xFF)
        # Controller fault/warning bits (289..290)
        regs[289] = 0
        regs[290] = 0
        for r in range(291, 300):
            regs[r] = 0

        # Parameter settings (0xE000 .. 0xE040 = 57344 .. 57408)
        sec_name = "dc_charger" if self.device_type == "RNG_DCC" else "rover"
        btype_str = self.config[sec_name].get("battery_type", "lithium").strip().lower()
        btype_val = BATTERY_TYPE_REVERSE.get(btype_str, 4)
        for r in range(57344, 57410):
            regs[r] = 0
        regs[57346] = 200  # Nominal battery capacity (200Ah)
        regs[57347] = (24 << 8) | 24  # System voltage setting (24V), recognized voltage (24V)
        regs[57348] = btype_val       # Battery type (1=open, 2=sealed, 3=gel, 4=lithium, 5=custom)
        regs[57349] = 160  # Overvoltage threshold 16.0V (per 12V unit)
        regs[57350] = 155  # Charging voltage limit 15.5V
        regs[57351] = 146  # Equalizing charging voltage 14.6V
        regs[57352] = 142  # Boost charging voltage 14.2V (Gel)
        regs[57353] = 138  # Floating charging voltage 13.8V
        regs[57354] = 132  # Boost recovery voltage 13.2V
        regs[57355] = 126  # Over-discharge recovery voltage 12.6V
        regs[57356] = 120  # Under-voltage warning level 12.0V
        regs[57357] = 111  # Over-discharge voltage 11.1V
        regs[57358] = 106  # Discharging limit voltage 10.6V
        regs[57360] = 5    # Over-discharge time delay 5s
        regs[57361] = 120  # Equalizing charging time 120 min
        regs[57362] = 120  # Boost charging time 120 min
        regs[57363] = 30   # Equalizing charging interval 30 days
        regs[57364] = 5    # Temperature compensation factor
        regs[57391] = 0    # Load working mode (57391 = 0xE02F)

        return regs

    def _build_read_payload(self, reg_addr: int, words: int) -> Optional[bytearray]:
        """Build the data bytes (length = words * 2) for a given register and word count."""
        data = bytearray(words * 2)

        # 1. Rover / Wanderer / Adventurer / DCCharger shared registers
        if reg_addr == 12 and words == 8:
            # 16-byte ASCII model name
            if self.device_type == "RNG_DCC":
                model = self.config["dc_charger"].get("model", "RBC50D1S-G1")
            else:
                model = self.config["emulator"].get("model", "RNG-CTRL-ROVER60")
            model_bytes = model.encode("utf-8")[:16].ljust(16, b" ")
            data[0:16] = model_bytes
            return data

        if reg_addr == 26 and words == 1:
            dev_id = (
                self.config["dc_charger"].getint("device_id", self.device_id)
                if self.device_type == "RNG_DCC"
                else self.device_id
            )
            data[0:2] = dev_id.to_bytes(2, "big")
            return data

        if reg_addr == 256 and words == 34:
            # Rover charging info (34 words = 68 bytes, indices 0..67 in data -> 3..70 in frame)
            sec = self.config["rover"]
            data[0:2] = int(float(sec.get("battery_percentage", "87"))).to_bytes(2, "big")
            data[2:4] = int(round(float(sec.get("battery_voltage", "12.9")) * 10)).to_bytes(2, "big")
            data[4:6] = int(round(float(sec.get("battery_current", "2.58")) * 100)).to_bytes(2, "big")
            ctrl_temp = int(float(sec.get("controller_temperature", "33")))
            batt_temp = int(float(sec.get("battery_temperature", "25")))
            data[6] = encode_temperature_byte(ctrl_temp)  # frame offset 9
            data[7] = encode_temperature_byte(batt_temp)  # frame offset 10
            data[8:10] = int(round(float(sec.get("load_voltage", "0.0")) * 10)).to_bytes(2, "big")
            data[10:12] = int(round(float(sec.get("load_current", "0.0")) * 100)).to_bytes(2, "big")
            data[12:14] = int(float(sec.get("load_power", "0"))).to_bytes(2, "big")
            data[14:16] = int(round(float(sec.get("pv_voltage", "17.1")) * 10)).to_bytes(2, "big")
            data[16:18] = int(round(float(sec.get("pv_current", "2.04")) * 100)).to_bytes(2, "big")
            data[18:20] = int(float(sec.get("pv_power", "35"))).to_bytes(2, "big")
            data[30:32] = int(float(sec.get("max_charging_power_today", "143"))).to_bytes(2, "big")
            data[32:34] = int(float(sec.get("max_discharging_power_today", "0"))).to_bytes(2, "big")
            data[34:36] = int(float(sec.get("charging_amp_hours_today", "34"))).to_bytes(2, "big")
            data[36:38] = int(float(sec.get("discharging_amp_hours_today", "34"))).to_bytes(2, "big")
            data[38:40] = int(float(sec.get("power_generation_today", "432"))).to_bytes(2, "big")
            data[40:42] = int(float(sec.get("power_consumption_today", "0"))).to_bytes(2, "big")
            data[56:60] = int(float(sec.get("power_generation_total", "426038"))).to_bytes(4, "big")
            load_on = 1 if sec.get("load_status", "off").strip().lower() in ("on", "1", "true") else self.load_status
            data[64] = (load_on & 1) << 7  # frame offset 67
            chg_state = ROVER_CHARGING_STATE_REVERSE.get(sec.get("charging_status", "mppt").strip().lower(), 2)
            data[65] = chg_state  # frame offset 68
            return data

        if reg_addr == 256 and words == 30:
            # DC Charger charging info (30 words = 60 bytes)
            sec = self.config["dc_charger"]
            data[0:2] = int(float(sec.get("battery_percentage", "100"))).to_bytes(2, "big")
            data[2:4] = int(round(float(sec.get("battery_voltage", "13.2")) * 10)).to_bytes(2, "big")
            data[4:6] = int(round(float(sec.get("combined_charge_current", "0.0")) * 100)).to_bytes(2, "big")
            ctrl_temp = int(float(sec.get("controller_temperature", "18")))
            batt_temp = int(float(sec.get("battery_temperature", "25")))
            data[6] = encode_temperature_byte(ctrl_temp)
            data[7] = encode_temperature_byte(batt_temp)
            data[8:10] = int(round(float(sec.get("alternator_voltage", "12.9")) * 10)).to_bytes(2, "big")
            data[10:12] = int(round(float(sec.get("alternator_current", "0.0")) * 100)).to_bytes(2, "big")
            data[12:14] = int(float(sec.get("alternator_power", "0"))).to_bytes(2, "big")
            data[14:16] = int(round(float(sec.get("pv_voltage", "0.0")) * 10)).to_bytes(2, "big")
            data[16:18] = int(round(float(sec.get("pv_current", "0.0")) * 100)).to_bytes(2, "big")
            data[18:20] = int(float(sec.get("pv_power", "0"))).to_bytes(2, "big")
            data[22:24] = int(round(float(sec.get("battery_min_voltage_today", "13.2")) * 10)).to_bytes(2, "big")
            data[24:26] = int(round(float(sec.get("battery_max_voltage_today", "13.3")) * 10)).to_bytes(2, "big")
            data[26:28] = int(round(float(sec.get("battery_max_current_today", "17.02")) * 100)).to_bytes(2, "big")
            data[30:32] = int(float(sec.get("max_charging_power_today", "238"))).to_bytes(2, "big")
            data[34:36] = int(float(sec.get("charging_amp_hours_today", "25"))).to_bytes(2, "big")
            data[38:40] = int(float(sec.get("power_generation_today", "336"))).to_bytes(2, "big")
            data[42:44] = int(float(sec.get("total_working_days", "703"))).to_bytes(2, "big")
            data[44:46] = int(float(sec.get("count_battery_overdischarged", "0"))).to_bytes(2, "big")
            data[46:48] = int(float(sec.get("count_battery_fully_charged", "1435"))).to_bytes(2, "big")
            data[48:52] = int(float(sec.get("battery_ah_total_accumulated", "5607"))).to_bytes(4, "big")
            data[56:60] = int(float(sec.get("power_generation_total", "76580"))).to_bytes(4, "big")
            return data

        if reg_addr == 288 and words == 3:
            # DC Charger state & alarms
            err = self.config["dc_charger"].get("error", "").strip().lower()
            if err == "battery_over_discharge":
                data[3] = 1  # frame offset 6
            return data

        if reg_addr == 57348 and words == 1:
            sec_name = "dc_charger" if self.device_type == "RNG_DCC" else "rover"
            btype_str = self.config[sec_name].get("battery_type", "lithium").strip().lower()
            btype_val = BATTERY_TYPE_REVERSE.get(btype_str, 4)
            data[0:2] = btype_val.to_bytes(2, "big")
            return data

        # 2. Rover Historical Data (registers 61440..61470, 10 words each)
        if 61440 <= reg_addr <= 61470 and words == 10:
            day_index = 61446 - reg_addr if reg_addr <= 61446 else (reg_addr - 61440)
            sec = self.config["rover"]
            gen_list = [int(x.strip()) for x in sec.get("daily_power_generation", "").split(",") if x.strip()]
            ah_list = [int(x.strip()) for x in sec.get("daily_charge_ah", "").split(",") if x.strip()]
            maxp_list = [int(x.strip()) for x in sec.get("daily_max_power", "").split(",") if x.strip()]

            gen_val = gen_list[day_index % len(gen_list)] if gen_list else 0
            ah_val = ah_list[day_index % len(ah_list)] if ah_list else 0
            maxp_val = maxp_list[day_index % len(maxp_list)] if maxp_list else 0

            data[8:10] = maxp_val.to_bytes(2, "big")  # frame offset 11..13
            data[12:14] = ah_val.to_bytes(2, "big")   # frame offset 15..17
            data[16:18] = gen_val.to_bytes(2, "big")  # frame offset 19..21
            return data

        # Generic Rover register bank fallback (supports any start register & word count in 0..300 or 57344..57410)
        if self.device_type in ("RNG_CTRL", "RNG_CTRL_HIST") and (
            (10 <= reg_addr <= 300) or (57344 <= reg_addr <= 57410)
        ):
            rover_regs = self._build_rover_register_map()
            for i in range(words):
                word_val = rover_regs.get(reg_addr + i, 0) & 0xFFFF
                data[i * 2 : i * 2 + 2] = word_val.to_bytes(2, "big")
            return data

        # 3. Smart Battery (RNG_BATT)
        if reg_addr == 5000 and words == 17:
            sec = self.config["battery"]
            cell_count = int(sec.get("cell_count", "4"))
            voltages = [float(x.strip()) for x in sec.get("cell_voltages", "3.6, 3.6, 3.6, 3.6").split(",") if x.strip()]
            data[0:2] = cell_count.to_bytes(2, "big")
            for i in range(min(cell_count, 16)):
                v = voltages[i] if i < len(voltages) else 3.6
                data[2 + i * 2 : 4 + i * 2] = int(round(v * 10)).to_bytes(2, "big")
            return data

        if reg_addr == 5017 and words == 17:
            sec = self.config["battery"]
            sensor_count = int(sec.get("sensor_count", "4"))
            temps = [float(x.strip()) for x in sec.get("temperatures", "21.0, 21.0, 21.0, 21.0").split(",") if x.strip()]
            data[0:2] = sensor_count.to_bytes(2, "big")
            for i in range(min(sensor_count, 16)):
                t = temps[i] if i < len(temps) else 21.0
                data[2 + i * 2 : 4 + i * 2] = int(round(t * 10)).to_bytes(2, "big", signed=True)
            return data

        if reg_addr == 5042 and words == 6:
            sec = self.config["battery"]
            data[0:2] = int(round(float(sec.get("current", "1.4")) * 100)).to_bytes(2, "big", signed=True)
            data[2:4] = int(round(float(sec.get("voltage", "14.5")) * 10)).to_bytes(2, "big")
            data[4:8] = int(round(float(sec.get("remaining_charge", "99.941")) * 1000)).to_bytes(4, "big")
            data[8:12] = int(round(float(sec.get("capacity", "100.0")) * 1000)).to_bytes(4, "big")
            return data

        if reg_addr == 5122 and words == 8:
            model = self.config["battery"].get("model", "RBT100LFP12S-G")
            data[0:16] = model.encode("utf-8")[:16].ljust(16, b"\x00")
            return data

        if reg_addr == 5223 and words == 1:
            dev_id = self.config["battery"].getint("device_id", 48)
            data[0:2] = dev_id.to_bytes(2, "big")
            return data

        # 4. Inverter (RNG_INVT) and HF Inverter (RNG_INVT_HF)
        if reg_addr == 4000 and words == 10:
            sec = self.config["inverter"]
            data[0:2] = int(round(float(sec.get("input_voltage", "124.9")) * 10)).to_bytes(2, "big")
            data[2:4] = int(round(float(sec.get("input_current", "2.2")) * 100)).to_bytes(2, "big")
            data[4:6] = int(round(float(sec.get("output_voltage", "124.9")) * 10)).to_bytes(2, "big")
            data[6:8] = int(round(float(sec.get("output_current", "1.19")) * 100)).to_bytes(2, "big")
            data[8:10] = int(round(float(sec.get("output_frequency", "59.97")) * 100)).to_bytes(2, "big")
            data[10:12] = int(round(float(sec.get("battery_voltage", "14.4")) * 10)).to_bytes(2, "big")
            data[12:14] = int(round(float(sec.get("temperature", "30.0")) * 10)).to_bytes(2, "big")
            data[18:20] = int(round(float(sec.get("input_frequency", "59.97")) * 100)).to_bytes(2, "big")
            return data

        if reg_addr == 4000 and words == 7:
            sec = self.config["hf_inverter"]
            data[0:2] = int(round(float(sec.get("ac_input_voltage", "230.5")) * 10)).to_bytes(2, "big")
            data[2:4] = int(round(float(sec.get("ac_input_frequency", "50.0")) * 10)).to_bytes(2, "big")
            data[4:6] = int(round(float(sec.get("ac_voltage_setting", "230.0")) * 10)).to_bytes(2, "big")
            data[6:8] = int(round(float(sec.get("battery_discharge_current", "15.5")) * 10)).to_bytes(2, "big")
            data[10:12] = int(round(float(sec.get("battery_temperature", "25.0")) * 10)).to_bytes(2, "big")
            data[12:14] = int(round(float(sec.get("internal_temperature", "35.0")) * 10)).to_bytes(2, "big")
            return data

        if reg_addr == 4109 and words == 1:
            sec_name = "hf_inverter" if self.device_type == "RNG_INVT_HF" else "inverter"
            dev_id = self.config[sec_name].getint("device_id", 32)
            data[0:2] = dev_id.to_bytes(2, "big")
            return data

        if reg_addr == 4301 and words == 1:
            ac_pres = self.config["hf_inverter"].getint("ac_input_present", 1)
            data[0:2] = ac_pres.to_bytes(2, "big")
            return data

        if reg_addr == 4311 and words == 8:
            sec_name = "hf_inverter" if self.device_type == "RNG_INVT_HF" else "inverter"
            model = self.config[sec_name].get("model", "RIV1230RCH-SPS")
            data[0:16] = model.encode("utf-8")[:16].ljust(16, b"\x00")
            return data

        if reg_addr == 4327 and words == 7:
            sec = self.config["inverter"]
            data[0:2] = int(float(sec.get("battery_percentage", "100"))).to_bytes(2, "big")
            data[2:4] = int(round(float(sec.get("charging_current", "0.7")) * 10)).to_bytes(2, "big", signed=True)
            data[4:6] = int(round(float(sec.get("solar_voltage", "0.0")) * 10)).to_bytes(2, "big")
            data[6:8] = int(round(float(sec.get("solar_current", "0.0")) * 10)).to_bytes(2, "big")
            data[8:10] = int(float(sec.get("solar_power", "0"))).to_bytes(2, "big")
            chg_state = INVERTER_CHARGING_STATE_REVERSE.get(sec.get("charging_status", "deactivated").strip().lower(), 0)
            data[10:12] = chg_state.to_bytes(2, "big")
            data[12:14] = int(float(sec.get("charging_power", "10"))).to_bytes(2, "big")
            return data

        if reg_addr == 4328 and words == 6:
            sec = self.config["hf_inverter"]
            data[0:2] = int(round(float(sec.get("battery_current", "-12.5")) * 10)).to_bytes(2, "big", signed=True)
            data[8:10] = int(float(sec.get("charging_active", "1"))).to_bytes(2, "big")
            data[10:12] = int(round(float(sec.get("charging_power_amps", "12.5")) * 10)).to_bytes(2, "big")
            return data

        if reg_addr == 4408 and words == 6:
            sec = self.config["inverter"]
            data[0:2] = int(round(float(sec.get("load_current", "1.2")) * 10)).to_bytes(2, "big")
            data[2:4] = int(float(sec.get("load_active_power", "108"))).to_bytes(2, "big")
            data[4:6] = int(float(sec.get("load_apparent_power", "150"))).to_bytes(2, "big")
            data[8:10] = int(round(float(sec.get("line_charging_current", "0.0")) * 10)).to_bytes(2, "big")
            data[10:12] = int(float(sec.get("load_percentage", "5"))).to_bytes(2, "big")
            return data

        if reg_addr == 4405 and words == 18:
            sec = self.config["hf_inverter"]
            data[0:2] = int(float(sec.get("operating_mode", "4"))).to_bytes(2, "big")
            data[14:16] = int(round(float(sec.get("charging_current", "20.0")) * 10)).to_bytes(2, "big")
            data[34:36] = int(round(float(sec.get("max_charging_current_setting", "50.0")) * 10)).to_bytes(2, "big")
            return data

        return None

    def build_shunt_notification(self) -> bytearray:
        """Build an 80-byte notification payload for Smart Shunt (RNG_SHNT)."""
        sec = self.config["shunt"]
        payload = bytearray(80)
        payload[0] = 0x42
        payload[1] = 87  # SHUNT_READ_SUCCESS
        charge_amps = int(round(float(sec.get("charge_amps", "0.02")) * 1000))
        main_v = int(round(float(sec.get("main_battery_voltage", "13.21")) * 1000))
        starter_v = int(round(float(sec.get("starter_battery_voltage", "0.0")) * 1000))
        percent = int(round(float(sec.get("main_battery_percent", "100.0")) * 10))
        temp_c = int(round(float(sec.get("battery_temperature", "19.9")) * 10))

        payload[21:24] = charge_amps.to_bytes(3, "big", signed=True)
        payload[25:28] = main_v.to_bytes(3, "big")
        payload[30:32] = starter_v.to_bytes(2, "big")
        payload[34:36] = percent.to_bytes(2, "big")
        payload[66:68] = temp_c.to_bytes(2, "big", signed=True)
        return payload
