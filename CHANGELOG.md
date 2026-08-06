# Changelog

## 2.1.0-beta.1

- Add model code, serial number, and firmware version to Home Assistant device information.
- Cache static charger identity registers after the first successful read.
- Add redacted Home Assistant diagnostics support.
- Add HACS and Hassfest validation workflow.
- Keep the firmware 1.6 FC16 write fix and individual configuration-register reads from alpha 1.

## 2.1.0-alpha.1

- Initial firmware 1.6 compatibility release.
- Use FC16 for readable/writable registers in the `0x3000` range.
- Read configuration registers individually to avoid Modbus exception `0x02`.
