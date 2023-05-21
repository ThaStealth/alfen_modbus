
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

# home-assistant-alfen-modbus
Home assistant Custom Component for reading data from Alfen EV NG9xx charger through modbus TCP.
Implements Inverter registers from the [Alfen Modbus Slave TCP/IP protocol][1] 
# Installation
Copy contents of custom_components folder to your home-assistant config/custom_components folder or install through HACS.
After reboot of Home-Assistant, this integration can be configured through the integration setup UI

# Enabling Modbus TCP on Alfen EV Charger
1. Ensure you have aquired the "Active load balancing" license which enables modbus communication for your EV charger. 
2. Enable "Active Load Balacing" via the Alfen Service installer application. 

# Configure power budget (Slave role)
Select the "Energy Management System" option in the Active balancing -> Data source field. 


# Smart Charging Network
SCN is used in a multi charging station situation (parking lots). The SCN fields are not yet fully implemented.

[1]: https://alfen.com/file-download/download/public/1610

