# Alfen Modbus for Home Assistant

[![HACS Default](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/straybiker/alfen_modbus)](https://github.com/straybiker/alfen_modbus/releases)
[![License](https://img.shields.io/github/license/straybiker/alfen_modbus)](LICENSE)

Home Assistant integration for **Alfen Eve NG9xx** series EV chargers via Modbus TCP.

![Demo](demo.png)

## Features

- 🔌 **Real-time monitoring** - Voltage, current, power, energy for all phases
- 🚗 **Car status detection** - Connected, charging, disconnected states
- ⚡ **Load balancing control** - Set maximum charging current dynamically
- �️ **Max current protection** - Prevents setting current above station limit
- �📊 **Session tracking** - Energy consumed and duration per charging session
- 🔄 **Auto-renew max current** - Prevents timeout to safe current mode
- 🏢 **Multi-socket support** - Works with dual socket chargers
- 🌐 **SCN support** - Smart Charging Network (partial)

## Requirements

- Home Assistant **2024.4.0** or newer
- Alfen Eve NG9xx charger with:
  - Firmware **4.2.0** or newer (Modbus TCP support)
  - Firmware **6.4.0+** recommended (fixes power budget reset bug)
  - **Active Load Balancing** license enabled
- Modbus TCP enabled on the charger

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Search for "Alfen Modbus"
3. Click Install
4. Restart Home Assistant

### Manual

1. Copy `custom_components/alfen_modbus` to your `config/custom_components/` folder
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **Alfen Modbus**
4. Enter your charger's IP address and port (default: 502)

## Enabling Modbus on Alfen Charger

1. Acquire the **Active Load Balancing** license from Alfen
2. Enable **Active Load Balancing** via the Alfen Service Installer app
3. Set **Data Source** to "Energy Management System" for slave mode

See the [Alfen Smart Charging Manual](https://knowledge.alfen.com/space/IN/639762449) for details.

## Sensors

| Category | Sensors |
|----------|---------|
| **Device** | Name, Manufacturer, Serial, Firmware, Platform |
| **Station** | Max Current, Temperature, Backoffice Connection |
| **Socket** | Voltages (L1-N, L2-N, L3-N, L1-L2, L2-L3, L3-L1) |
| | Currents (L1, L2, L3, N, Sum) |
| | Power (Real, Apparent, Reactive per phase + Sum) |
| | Energy (Delivered, Consumed per phase + Sum) |
| | Mode 3 State, Availability, Charging Phases |
| **Derived** | Car Connected, Car Charging, Session Wh, Session Duration |

## Controls

| Control | Description |
|---------|-------------|
| **Max Current** | Set the maximum charging current (load balancing) |
| **Phase Mode** | Select 1-phase or 3-phase charging |

## Known Issues

- Power budget may reset to 0A when no car is connected (fixed in firmware [6.4.0-4210](https://knowledge.alfen.com/space/IN/243466257))
- **Reallin power meter (post-2021)**: Chargers with a Reallin power meter produced after 2021 only export a subset of measurement values. Per-phase energy, apparent energy, and reactive energy sensors will show as "unavailable" (NaN). This is a hardware limitation, not a bug.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Changelog

### v1.0.0

- **Stable release** - First stable release for HACS
- **Binary sensors** - Added `car_connected` and `car_charging` binary sensors
- **Improved config flow** - Enhanced UI with descriptions and connection testing
- **Options flow** - Reconfigure host, port, and settings after setup
- **pymodbus 3.11 compatibility** - Updated API calls for latest pymodbus

### v0.2.0

- **Max current protection** - The max current slider now dynamically limits to the station's actual max current (Register 1100), preventing values higher than the hardware allows
- **pymodbus 3.11 compatibility** - Updated API calls to use `device_id` parameter (replaces deprecated `slave`)

### v0.1.9

- Initial release

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.
