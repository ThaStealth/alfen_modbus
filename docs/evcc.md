# EVCC Configuration Guide

Step-by-step setup for the **Home Assistant Charger** template in [EVCC](https://evcc.io)'s web configuration UI, using entities from this integration.

EVCC's configurator auto-discovers Home Assistant instances on your network and suggests matching `sensor.*`, `binary_sensor.*`, `switch.*` and `number.*` entities as you type. Go to **Configuration → Charger → Add charger** and pick **Home Assistant Charger**, then fill in the fields below.

## Basic settings

| Field | Value | Notes |
|---|---|---|
| Home Assistant URI | `http://homeassistant.local:8123` | Your own Home Assistant base URL. |
| Charging status sensor | `sensor.alfen_mode_3_state` | Raw IEC 61851 Mode 3 state (`A`, `B1`, `B2`, `C1`, `C2`, `D1`, `D2`, `E`, `F`). Requires the state overrides below so EVCC can map it to its own A/B/C model. |
| Enabled status sensor | `binary_sensor.alfen_charger_enabled` | On when the max-current setpoint is above 0 A. |
| Enable switch | `switch.alfen_charger_enabled` | Off writes 0 A to the max-current register; on restores the station's currently allowed max current. |
| Maximum current entity [A] | `number.alfen_max_current_limit_s1` | Must be this **writable** `number` entity — not the read-only `sensor.alfen_actual_max_current`, which the domain filter on this field won't even list. |

With **Read Socket 2** enabled on the integration, use the `_socket_2` suffixed entities for a second charger instance (e.g. `switch.alfen_charger_enabled_socket_2`).

## Advanced settings

Click **Toon geavanceerde instellingen** / **Show advanced settings** to reveal the remaining fields:

| Field | Value | Notes |
|---|---|---|
| States for status A | `E,F` | Error / EVSE-disabled states, grouped with "ready". |
| States for status B | `B1,B2,C1,D1` | Connected but not drawing current. |
| States for status C | `C2,D2` | Actively charging (PWM applied). |
| Power entity | `sensor.alfen_real_power_sum` | |
| Energy entity | `sensor.alfen_real_energy_delivered_sum` | Reported in Wh; add a template sensor to convert to kWh if EVCC doesn't scale it for you. |
| L1 / L2 / L3 current entity | `sensor.alfen_current_l1` / `_l2` / `_l3` | |
| L1 / L2 / L3 voltage entity | `sensor.alfen_voltage_l1_n` / `_l2_n` / `_l3_n` | |
| Phase switching entity | `select.alfen_usable_phases` | Options are the literal values `"1"` and `"3"`. |

## Caveats

- Alfen has no dedicated enable/disable coil — the charger-enabled switch and sensor are both derived from the max-current setpoint (register 1210). Turning charging off/on this way is equivalent to setting `number.alfen_max_current_limit_s1` to 0 A or back to its allowed maximum. Don't drive both the switch and the number entity from your own automations at the same time, or they'll fight each other's setpoints.
- Click **valideer** (validate) after filling in the fields to confirm EVCC can reach Home Assistant and read every entity before saving.
