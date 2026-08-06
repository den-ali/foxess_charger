# FoxESS EV Charger for Home Assistant

Custom Home Assistant integration for FoxESS A-series EV chargers over local Modbus TCP, including firmware 1.6 compatibility.

## Highlights

- Local polling; no cloud required.
- Status, voltage, current, power, energy, temperatures, alarms, and faults.
- Work mode, current/power limits, locking, charging control, and automatic phase switching.
- Firmware 1.6 protocol handling:
  - FC16 (`0x10`) for readable/writable registers.
  - FC06 (`0x06`) for write-only command registers.
  - Individual reads for configuration registers that reject a block read.
- Model, serial number, and firmware in Home Assistant Device Info.
- Redacted diagnostics download.
- HACS-compatible repository structure.

## Install through HACS as a custom repository

1. Open HACS.
2. Open the menu and choose **Custom repositories**.
3. Add `https://github.com/den-ali/foxess_charger` as category **Integration**.
4. Install **FoxESS EV Charger**.
5. Restart Home Assistant.
6. Add the integration through **Settings → Devices & services → Add integration**.

For a GitHub release, copy the contents of this package to the repository root, commit it, and create a full GitHub release with the same version as `manifest.json`.

## Connection defaults

- Modbus TCP unit ID: `1`
- Integration default port: `1502`
- FoxESS protocol documentation default port: `502`

Use the port exposed by your charger. Existing working installations should keep their current port.

## Firmware 1.6 status

Reading and writing configuration values has been tested on a FoxESS A-series 22 kW charger after firmware 1.6. Charging start/stop and live charging transitions still require testing with a vehicle connected.
