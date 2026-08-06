"""Shared entity helpers for the FoxESS EV Charger integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


def charger_device_info(entry: ConfigEntry, data: dict | None) -> DeviceInfo:
    """Return device information populated from protocol 1.6 identity registers."""
    values = data or {}
    model = values.get("model_code") or "EV Charger"
    serial = values.get("serial_number") or None
    software = values.get("software_version_text") or None

    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="FoxESS EV Charger",
        manufacturer="FoxESS",
        model=model,
        serial_number=serial,
        sw_version=software,
    )
