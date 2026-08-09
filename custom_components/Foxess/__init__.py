"""FoxESS EV Charger integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN, PLATFORMS,
    CONF_HOST, CONF_PORT, CONF_SLAVE_ID,
    DEFAULT_SCAN_INTERVAL,
)
from .modbus_client import FoxESSModbusClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    host      = entry.data[CONF_HOST]
    port      = entry.data[CONF_PORT]
    slave_id  = entry.data[CONF_SLAVE_ID]
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)

    client      = FoxESSModbusClient(host, port, slave_id)
    coordinator = FoxESSChargerCoordinator(hass, client, scan_interval)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client":      client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await hass.async_add_executor_job(data["client"].disconnect)
    return unload_ok


class FoxESSChargerCoordinator(DataUpdateCoordinator):
    """Coordinator: pollt alle Modbus-Register des Chargers."""

    def __init__(self, hass: HomeAssistant, client: FoxESSModbusClient,
                 scan_interval: int) -> None:
        self.client = client
        self._identity: dict[str, str] = {}
        super().__init__(
            hass, _LOGGER, name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict:
        try:
            return await self.hass.async_add_executor_job(self._fetch)
        except Exception as err:
            raise UpdateFailed(f"Modbus error: {err}") from err

    @staticmethod
    def _format_software_version(raw: int | None) -> str | None:
        if raw is None:
            return None
        return f"{raw >> 8}.{raw & 0xFF}"

    def _fetch(self) -> dict:
        data: dict = dict(self._identity)

        # ── 0x1000–0x1015: 22 Status-Register ────────────────────────────────
        regs = self.client.read_registers(0x1000, 22)
        if regs and len(regs) >= 22:
            data["device_address"]  = regs[0]
            data["software_version"]= regs[1]
            data["software_version_text"] = self._format_software_version(regs[1])
            data["stop_reason"]     = regs[2]
            data["status"]          = regs[3]
            data["cp_status"]       = regs[4]
            data["cc_status"]       = regs[5]
            data["port_temp_raw"]   = regs[6]
            data["ambient_temp_raw"]= regs[7]
            data["l1_voltage_raw"]  = regs[8]
            data["l2_voltage_raw"]  = regs[9]
            data["l3_voltage_raw"]  = regs[10]
            data["l1_current_raw"]  = regs[11]
            data["l2_current_raw"]  = regs[12]
            data["l3_current_raw"]  = regs[13]
            data["power_raw"]       = regs[14]
            data["lock_status"]     = regs[15]
            data["phase_sequence"]  = regs[16]
            data["max_power_raw"]   = regs[17]
            data["min_power_raw"]   = regs[18]
            data["max_current_raw"] = regs[19]
            data["min_current_raw"] = regs[20]
            data["alarm_code"]      = regs[21]
        else:
            _LOGGER.warning("Could not read status registers 0x1000–0x1015")

        # Identity registers are static, so read and cache them once.
        if not self._identity:
            model = self.client.read_ascii(0x101E, 4)
            serial = self.client.read_ascii(0x1022, 16)
            if model:
                self._identity["model_code"] = model
                data["model_code"] = model
            if serial:
                self._identity["serial_number"] = serial
                data["serial_number"] = serial

        # ── 0x1016/0x1018/0x101A/0x101C: UINT32 Register ─────────────────────
        for key, addr in [
            ("current_energy_raw", 0x1016),
            ("total_energy_raw",   0x1018),
            ("fault_code",         0x101A),
            ("rfid_card",          0x101C),
        ]:
            val = self.client.read_uint32(addr)
            if val is not None:
                data[key] = val

        # Read protocol 1.6 R/W registers individually. Some firmware builds
        # reject a single block read spanning the 0x3008 UINT32 value and the
        # following address gap, returning exception 0x02 at 0x3000.
        config_registers = {
            "work_mode": 0x3000,
            "max_charging_current_raw": 0x3001,
            "max_charging_power_raw": 0x3002,
            "allowed_charge_time": 0x3003,
            "allowed_charge_energy": 0x3004,
            "time_validity": 0x3005,
            "default_current_raw": 0x3006,
            "auto_phase_switch": 0x300A,
            "min_switch_interval": 0x300B,
        }
        for key, address in config_registers.items():
            value = self.client.read_register(address)
            if value is not None:
                data[key] = value
            else:
                _LOGGER.debug("Register 0x%04X (%s) is unavailable", address, key)

        if not data:
            raise RuntimeError("FoxESS charger returned no readable register data")

        return data
