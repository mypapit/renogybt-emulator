# ==============================================================================
# librenogybt-emulator (renogybt-emulator)
# Copyright (c) 2026 Mohammad Hafiz bin Ismail (mypapit@gmail.com) - http://mypapit.net
# Licensed under the GNU General Public License version 3 (GNU/GPL v3).
#
# Inspired by Cyril Sebastian's renogy-bt (https://github.com/cyrils/renogy-bt)
# and designed to work seamlessly with it and other compatible Renogy BLE clients.
# ==============================================================================
"""CLI entrypoint for renogybt-emulator."""

import argparse
import asyncio
import logging
import os
import runpy
import signal
import sys
from typing import Optional

from .config import load_emulator_config
from .server import RenogyBLEEmulator


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="renogybt-emulator",
        description="Emulate a Renogy BT-1 / BT-2 BLE module (e.g. RNG-CTRL-ROVER60)",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="Path to emulator configuration file (.ini). Uses preset defaults if omitted.",
    )
    parser.add_argument(
        "--adapter",
        default=None,
        help="Override Bluetooth adapter name (e.g. hci0)",
    )
    parser.add_argument(
        "--alias",
        default=None,
        help="Override BLE device alias (e.g. BT-TH-66f9347E)",
    )
    parser.add_argument(
        "--mac",
        default=None,
        help="Override emulated MAC address (e.g. 80:6F:B0:66:F9:34)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override device model (default: RNG-CTRL-ROVER60)",
    )
    parser.add_argument(
        "--type",
        default=None,
        choices=["RNG_CTRL", "RNG_CTRL_HIST", "RNG_BATT", "RNG_INVT", "RNG_INVT_HF", "RNG_DCC", "RNG_SHNT"],
        help="Override device type (default: RNG_CTRL)",
    )
    parser.add_argument(
        "--mode",
        default=None,
        choices=["static", "cycle"],
        help="Emulator mode: 'static' (single state) or 'cycle' (rotate through 4 solar MPPT states)",
    )
    parser.add_argument(
        "--state-interval",
        default=None,
        help="Time between state transitions in 'cycle' mode (e.g. '30s', '10', '2m')",
    )
    parser.add_argument(
        "--initial-state",
        default=None,
        help="Initial state name when starting in 'cycle' mode (e.g. nighttime, early_morning, noon, late_afternoon)",
    )
    parser.add_argument(
        "--run-example",
        metavar="CLIENT_CONFIG_INI",
        default=None,
        help="Run example.py (or client config) against the in-process virtual BLE emulator and exit.",
    )
    parser.add_argument(
        "--example-script",
        default="example.py",
        help="Path to example.py when using --run-example (default: example.py)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser


async def _serve_bluez(emulator: RenogyBLEEmulator):
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    await emulator.start_bluez_server()
    logging.info("Press Ctrl+C to stop the emulator...")
    try:
        await stop_event.wait()
    finally:
        logging.info("Stopping Renogy BLE emulator...")
        await emulator.stop_bluez_server()


def main(argv: Optional[list] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s",
    )

    cfg = load_emulator_config(args.config)
    if args.adapter:
        cfg["emulator"]["adapter"] = args.adapter
    if args.alias:
        cfg["emulator"]["alias"] = args.alias
    if args.mac:
        cfg["emulator"]["mac_addr"] = args.mac
    if args.model:
        cfg["emulator"]["model"] = args.model
    if args.type:
        cfg["emulator"]["type"] = args.type
    if args.mode:
        cfg["emulator"]["mode"] = args.mode
    if args.state_interval:
        cfg["emulator"]["state_interval"] = str(args.state_interval)
        if not args.mode and cfg["emulator"].get("mode", "static") == "static":
            cfg["emulator"]["mode"] = "cycle"
    if args.initial_state:
        cfg["emulator"]["initial_state"] = args.initial_state

    emulator = RenogyBLEEmulator(config=cfg, config_path=args.config)

    if args.run_example:
        script_path = os.path.abspath(args.example_script)
        script_dir = os.path.dirname(script_path)
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        client_cfg_path = os.path.abspath(args.run_example)
        if not os.path.exists(script_path):
            logging.error("Example script not found: %s", script_path)
            return 1
        with emulator.virtual_ble_context():
            old_argv = sys.argv[:]
            try:
                sys.argv = [script_path, client_cfg_path]
                runpy.run_path(script_path, run_name="__main__")
            finally:
                sys.argv = old_argv
        return 0

    try:
        asyncio.run(_serve_bluez(emulator))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
