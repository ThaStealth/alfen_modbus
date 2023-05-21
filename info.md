
## ALFEN MODBUS TCP

Home assistant Custom Component for reading data from Alfen EV charger through modbus TCP. Implements Inverter registers from  https://alfen.com/file-download/download/public/1610

### Features

- Installation through Config Flow UI.
- Separate sensor per register
-  Derived sensors to detect car is connected and car is charging
- Derived sensors for current charging session (duration and Wh consumed)
- Support for configuring max charging speed (load balancing)
- Auto renew max charging speed
- Configurable polling interval
- Support for Alfen Double EV chargers
- Supports multiple phases EV chargers

### Configuration
Go to the integrations page in your configuration and click on new integration -> Alfen Modbus

<img style="border: 5px solid #767676;border-radius: 10px;max-width: 350px;width: 100%;box-sizing: border-box;" src="https://github.com/ThaStealth/alfen_homeassistant/blob/master/demo.png?raw=true" alt="Demo">
