# ==============================================================================
# librenogybt-emulator (renogybt-emulator)
# Copyright (c) 2026 Mohammad Hafiz bin Ismail (mypapit@gmail.com) - http://mypapit.net
# Licensed under the GNU General Public License version 3 (GNU/GPL v3).
#
# Inspired by Cyril Sebastian's renogy-bt (https://github.com/cyrils/renogy-bt)
# and designed to work seamlessly with it and other compatible Renogy BLE clients.
# ==============================================================================
"""BLE GATT Peripheral Server and In-Process Loopback Transport for librenogybt-emulator."""

import asyncio
import configparser
import logging
from contextlib import contextmanager
from typing import Callable, Dict, List, Optional
from unittest.mock import patch

from bleak.backends.device import BLEDevice
from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, method, dbus_property, PropertyAccess
from dbus_fast import Variant, BusType, Message, MessageType

from .config import load_emulator_config
from .modbus import RenogyModbusDevice

logger = logging.getLogger(__name__)

WRITE_SERVICE_UUID = "0000ffd0-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID = "0000ffd1-0000-1000-8000-00805f9b34fb"
NOTIFY_SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
SHUNT_SERVICE_UUID = "0000c410-0000-1000-8000-00805f9b34fb"
SHUNT_NOTIFY_CHAR_UUID = "0000c411-0000-1000-8000-00805f9b34fb"

BLUEZ_SERVICE_NAME = "org.bluez"
GATT_MANAGER_IFACE = "org.bluez.GattManager1"
LE_ADV_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
GATT_SERVICE_IFACE = "org.bluez.GattService1"
GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
LE_ADVERTISEMENT_IFACE = "org.bluez.LEAdvertisement1"
OBJECT_MANAGER_IFACE = "org.freedesktop.DBus.ObjectManager"
ADAPTER_IFACE = "org.bluez.Adapter1"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"


class _BluezGattService(ServiceInterface):
    def __init__(self, path: str, uuid: str, primary: bool = True):
        super().__init__(GATT_SERVICE_IFACE)
        self.path = path
        self._uuid = uuid
        self._primary = primary

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":
        return self._uuid

    @dbus_property(access=PropertyAccess.READ)
    def Primary(self) -> "b":
        return self._primary

    def get_properties(self) -> Dict[str, Variant]:
        return {
            "UUID": Variant("s", self._uuid),
            "Primary": Variant("b", self._primary),
        }


class _BluezGattCharacteristic(ServiceInterface):
    def __init__(
        self,
        path: str,
        uuid: str,
        service_path: str,
        flags: List[str],
        on_write: Optional[Callable[[bytes], None]] = None,
        on_start_notify: Optional[Callable[[], None]] = None,
    ):
        super().__init__(GATT_CHRC_IFACE)
        self.path = path
        self._uuid = uuid
        self._service_path = service_path
        self._flags = flags
        self._value = b""
        self._notifying = False
        self._on_write = on_write
        self._on_start_notify = on_start_notify

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":
        return self._uuid

    @dbus_property(access=PropertyAccess.READ)
    def Service(self) -> "o":
        return self._service_path

    @dbus_property(access=PropertyAccess.READ)
    def Value(self) -> "ay":
        return self._value

    @dbus_property(access=PropertyAccess.READ)
    def Notifying(self) -> "b":
        return self._notifying

    @dbus_property(access=PropertyAccess.READ)
    def Flags(self) -> "as":
        return self._flags

    @method()
    def ReadValue(self, options: "a{sv}") -> "ay":
        return self._value

    @method()
    def WriteValue(self, value: "ay", options: "a{sv}"):
        self._value = bytes(value)
        if self._on_write:
            self._on_write(self._value)

    @method()
    def StartNotify(self):
        self._notifying = True
        if self._on_start_notify:
            self._on_start_notify()

    @method()
    def StopNotify(self):
        self._notifying = False

    def send_notification(self, data: bytes):
        self._value = bytes(data)
        self.emit_properties_changed({"Value": self._value})

    def get_properties(self) -> Dict[str, Variant]:
        return {
            "UUID": Variant("s", self._uuid),
            "Service": Variant("o", self._service_path),
            "Value": Variant("ay", self._value),
            "Notifying": Variant("b", self._notifying),
            "Flags": Variant("as", self._flags),
        }


class _BluezAdvertisement(ServiceInterface):
    def __init__(self, path: str, local_name: str, service_uuids: List[str]):
        super().__init__(LE_ADVERTISEMENT_IFACE)
        self.path = path
        self._local_name = local_name
        self._service_uuids = service_uuids

    @dbus_property(access=PropertyAccess.READ)
    def Type(self) -> "s":
        return "peripheral"

    @dbus_property(access=PropertyAccess.READ)
    def LocalName(self) -> "s":
        return self._local_name

    @dbus_property(access=PropertyAccess.READ)
    def ServiceUUIDs(self) -> "as":
        return self._service_uuids

    @method()
    def Release(self):
        logger.info("BLE Advertisement released by BlueZ")


class _BluezApplicationManager(ServiceInterface):
    def __init__(self, path: str, services: List[_BluezGattService], characteristics: List[_BluezGattCharacteristic]):
        super().__init__(OBJECT_MANAGER_IFACE)
        self.path = path
        self._services = services
        self._characteristics = characteristics

    @method()
    def GetManagedObjects(self) -> "a{oa{sa{sv}}}":
        objs = {}
        for svc in self._services:
            objs[svc.path] = {GATT_SERVICE_IFACE: svc.get_properties()}
        for chrc in self._characteristics:
            objs[chrc.path] = {GATT_CHRC_IFACE: chrc.get_properties()}
        return objs


class RenogyBLEEmulator:
    """Renogy BT-1 / BT-2 BLE Emulator supporting both BlueZ peripheral advertising and virtual loopback."""

    def __init__(self, config: Optional[configparser.ConfigParser] = None, config_path: Optional[str] = None):
        if config is None:
            config = load_emulator_config(config_path)
        self.config = config
        self.config_path = config_path
        self.modbus = RenogyModbusDevice(self.config, config_path=config_path)
        self.adapter = self.config["emulator"].get("adapter", "hci0").strip()
        self.mac_address = self.config["emulator"].get("mac_addr", "80:6F:B0:66:F9:34").strip().upper()
        self.alias = self.config["emulator"].get("alias", "BT-TH-66f9347E").strip()
        self.device_type = self.config["emulator"].get("type", "RNG_CTRL").strip()

        self._bus: Optional[MessageBus] = None
        self._notify_chrc: Optional[_BluezGattCharacteristic] = None
        self._shunt_chrc: Optional[_BluezGattCharacteristic] = None
        self._running = False
        self._shunt_task: Optional[asyncio.Task] = None
        self._state_cycle_task: Optional[asyncio.Task] = None

    async def _run_state_cycle_loop(self):
        """Background loop that switches solar MPPT states every state_interval_sec."""
        try:
            while self._running and self.modbus.mode == "cycle" and self.modbus.states:
                interval = max(self.modbus.state_interval_sec, 0.05)
                await asyncio.sleep(interval)
                if not self._running:
                    break
                self.modbus.advance_state_if_due(force=True)
        except asyncio.CancelledError:
            pass

    async def _run_state_cycle_loop(self):
        """Background loop that switches solar MPPT states every state_interval_sec."""
        try:
            while self._running and self.modbus.mode == "cycle" and self.modbus.states:
                interval = max(self.modbus.state_interval_sec, 0.05)
                await asyncio.sleep(interval)
                if not self._running:
                    break
                self.modbus.advance_state_if_due(force=True)
        except asyncio.CancelledError:
            pass

    def process_write(self, data: bytes) -> Optional[bytearray]:
        """Process a write to 0000ffd1 and return the notification bytes for 0000fff1."""
        logger.info("Emulator received write (%d bytes): %s", len(data), list(data))
        response = self.modbus.handle_request(bytes(data))
        if response is not None:
            logger.info("Emulator sending notification (%d bytes): %s", len(response), response.hex())
        return response

    async def start_bluez_server(self):
        """Register the GATT Application and LE Advertisement with BlueZ over system D-Bus."""
        self._bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        adapter_path = f"/org/bluez/{self.adapter}"
        app_path = "/org/renogybt/emulator"
        adv_path = "/org/renogybt/emulator/advertisement0"

        # Ensure adapter Alias matches the emulated device alias
        await self._bus.call(
            Message(
                destination=BLUEZ_SERVICE_NAME,
                path=adapter_path,
                interface=DBUS_PROP_IFACE,
                member="Set",
                signature="ssv",
                body=[ADAPTER_IFACE, "Alias", Variant("s", self.alias)],
            )
        )
        await self._bus.call(
            Message(
                destination=BLUEZ_SERVICE_NAME,
                path=adapter_path,
                interface=DBUS_PROP_IFACE,
                member="Set",
                body=[ADAPTER_IFACE, "Powered", Variant("b", True)],
                signature="ssv",
            )
        )

        # Build GATT services & characteristics
        svc_write = _BluezGattService(f"{app_path}/service0", WRITE_SERVICE_UUID, True)
        svc_notify = _BluezGattService(f"{app_path}/service1", NOTIFY_SERVICE_UUID, True)
        svc_shunt = _BluezGattService(f"{app_path}/service2", SHUNT_SERVICE_UUID, True)

        def on_gatt_write(value: bytes):
            resp = self.process_write(value)
            if resp is not None and self._notify_chrc is not None:
                loop = asyncio.get_running_loop()

                async def _send_framed(payload: bytes):
                    # Small delay to ensure client write_gatt_char completes before notify arrives
                    await asyncio.sleep(0.05)
                    self._notify_chrc.send_notification(payload)

                loop.create_task(_send_framed(bytes(resp)))

        def on_shunt_notify_start():
            if self.device_type == "RNG_SHNT" and self._shunt_chrc is not None:
                payload = self.modbus.build_shunt_notification()
                asyncio.get_running_loop().call_soon(self._shunt_chrc.send_notification, bytes(payload))

        chrc_write = _BluezGattCharacteristic(
            f"{app_path}/service0/char0",
            WRITE_CHAR_UUID,
            svc_write.path,
            ["write-without-response", "write"],
            on_write=on_gatt_write,
        )
        chrc_notify = _BluezGattCharacteristic(
            f"{app_path}/service1/char0",
            NOTIFY_CHAR_UUID,
            svc_notify.path,
            ["notify", "read"],
        )
        chrc_shunt = _BluezGattCharacteristic(
            f"{app_path}/service2/char0",
            SHUNT_NOTIFY_CHAR_UUID,
            svc_shunt.path,
            ["notify", "read"],
            on_start_notify=on_shunt_notify_start,
        )

        self._notify_chrc = chrc_notify
        self._shunt_chrc = chrc_shunt

        services = [svc_write, svc_notify, svc_shunt]
        characteristics = [chrc_write, chrc_notify, chrc_shunt]
        app_mgr = _BluezApplicationManager(app_path, services, characteristics)

        self._bus.export(app_path, app_mgr)
        for s in services:
            self._bus.export(s.path, s)
        for c in characteristics:
            self._bus.export(c.path, c)

        adv = _BluezAdvertisement(
            adv_path,
            local_name=self.alias,
            service_uuids=[WRITE_SERVICE_UUID, NOTIFY_SERVICE_UUID],
        )
        self._bus.export(adv_path, adv)

        # Register GATT Application
        reply = await self._bus.call(
            Message(
                destination=BLUEZ_SERVICE_NAME,
                path=adapter_path,
                interface=GATT_MANAGER_IFACE,
                member="RegisterApplication",
                signature="oa{sv}",
                body=[app_path, {}],
            )
        )
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(f"Failed to register GATT application: {reply.body}")

        # Register LE Advertisement
        reply = await self._bus.call(
            Message(
                destination=BLUEZ_SERVICE_NAME,
                path=adapter_path,
                interface=LE_ADV_MANAGER_IFACE,
                member="RegisterAdvertisement",
                signature="oa{sv}",
                body=[adv_path, {}],
            )
        )
        if reply.message_type == MessageType.ERROR:
            logger.warning(
                "LE Advertisement registration returned %s (adapter may already have an active connection/advertisement); GATT server remains active.",
                reply.body,
            )

        self._running = True
        if self.modbus.mode == "cycle" and self.modbus.states:
            self._state_cycle_task = asyncio.get_running_loop().create_task(self._run_state_cycle_loop())
        logger.info(
            "Renogy BLE Peripheral Server active on %s (%s) as '%s' [model=%s, type=%s, device_id=%s, mode=%s%s]",
            self.adapter,
            self.mac_address,
            self.alias,
            self.config["emulator"].get("model"),
            self.device_type,
            self.modbus.device_id,
            self.modbus.mode,
            f", state={self.modbus.current_state}, interval={self.modbus.state_interval_sec}s"
            if self.modbus.mode == "cycle"
            else "",
        )

    async def stop_bluez_server(self):
        """Unregister advertisement and GATT application from BlueZ."""
        self._running = False
        if self._state_cycle_task and not self._state_cycle_task.done():
            self._state_cycle_task.cancel()
        if self._shunt_task and not self._shunt_task.done():
            self._shunt_task.cancel()
        if self._bus:
            adapter_path = f"/org/bluez/{self.adapter}"
            app_path = "/org/renogybt/emulator"
            adv_path = "/org/renogybt/emulator/advertisement0"
            try:
                await self._bus.call(
                    Message(
                        destination=BLUEZ_SERVICE_NAME,
                        path=adapter_path,
                        interface=LE_ADV_MANAGER_IFACE,
                        member="UnregisterAdvertisement",
                        signature="o",
                        body=[adv_path],
                    )
                )
            except Exception:
                pass
            try:
                await self._bus.call(
                    Message(
                        destination=BLUEZ_SERVICE_NAME,
                        path=adapter_path,
                        interface=GATT_MANAGER_IFACE,
                        member="UnregisterApplication",
                        signature="o",
                        body=[app_path],
                    )
                )
            except Exception:
                pass
            self._bus.disconnect()
            self._bus = None

    @contextmanager
    def virtual_ble_context(self):
        """Context manager that patches BleakScanner and BleakClient so renogybt clients/example.py
        connect directly to this RenogyBLEEmulator instance on a single-adapter or no-adapter PC."""
        emulator = self

        class _VirtualCharacteristic:
            def __init__(self, uuid: str, handle: int):
                self.uuid = uuid
                self.handle = handle

        class _VirtualService:
            def __init__(self, uuid: str, characteristics: List[_VirtualCharacteristic]):
                self.uuid = uuid
                self.characteristics = characteristics

        class _VirtualBleakClient:
            def __init__(self, address_or_ble_device, disconnected_callback=None, **kwargs):
                self.device = address_or_ble_device
                self.address = (
                    address_or_ble_device.address
                    if hasattr(address_or_ble_device, "address")
                    else str(address_or_ble_device)
                )
                self._disconnected_callback = disconnected_callback
                self.is_connected = False
                self._notify_callbacks: Dict[str, Callable] = {}
                self._pending_tasks: List[asyncio.Task] = []
                self.services = [
                    _VirtualService(
                        WRITE_SERVICE_UUID,
                        [_VirtualCharacteristic(WRITE_CHAR_UUID, handle=0x0012)],
                    ),
                    _VirtualService(
                        NOTIFY_SERVICE_UUID,
                        [_VirtualCharacteristic(NOTIFY_CHAR_UUID, handle=0x0015)],
                    ),
                    _VirtualService(
                        SHUNT_SERVICE_UUID,
                        [_VirtualCharacteristic(SHUNT_NOTIFY_CHAR_UUID, handle=0x0018)],
                    ),
                ]

            async def connect(self, **kwargs):
                self.is_connected = True
                return True

            async def disconnect(self):
                self.is_connected = False
                for t in self._pending_tasks:
                    if not t.done() and t is not asyncio.current_task():
                        t.cancel()
                self._pending_tasks.clear()

            async def start_notify(self, characteristic, callback, **kwargs):
                char_uuid = characteristic.uuid if hasattr(characteristic, "uuid") else str(characteristic)
                self._notify_callbacks[char_uuid] = callback
                if char_uuid == SHUNT_NOTIFY_CHAR_UUID:
                    payload = emulator.modbus.build_shunt_notification()
                    t = asyncio.get_running_loop().create_task(callback(characteristic, payload))
                    self._pending_tasks.append(t)

            async def write_gatt_char(self, char_specifier, data, response=False):
                resp = emulator.process_write(bytes(data))
                if resp is not None and NOTIFY_CHAR_UUID in self._notify_callbacks:
                    cb = self._notify_callbacks[NOTIFY_CHAR_UUID]
                    t = asyncio.get_running_loop().create_task(cb(NOTIFY_CHAR_UUID, resp))
                    self._pending_tasks.append(t)

        async def _virtual_discover(timeout=5.0, **kwargs):
            return [
                BLEDevice(
                    address=emulator.mac_address,
                    name=emulator.alias,
                    details={"path": f"/org/bluez/{emulator.adapter}/dev_{emulator.mac_address.replace(':', '_')}"},
                )
            ]

        with patch("bleak.BleakScanner.discover", side_effect=_virtual_discover), patch(
            "bleak.BleakClient", _VirtualBleakClient
        ), patch("renogybt.BLEManager.BleakClient", _VirtualBleakClient, create=True):
            yield emulator
