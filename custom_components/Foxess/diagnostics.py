"""Diagnostics support for FoxESS EV Charger."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_HOST, DOMAIN

TO_REDACT = {CONF_HOST, "serial_number", "rfid_card"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a config entry."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime["coordinator"]

    return {
        "config_entry": async_redact_data(
            {
                "data": dict(entry.data),
                "options": dict(entry.options),
                "version": entry.version,
            },
            TO_REDACT,
        ),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval
                else None
            ),
            "data": async_redact_data(dict(coordinator.data or {}), TO_REDACT),
        },
        "protocol": "FoxESS EV Charger Modbus TCP 1.6",
    }
