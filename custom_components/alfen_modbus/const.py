DOMAIN = "alfen_modbus"
DEFAULT_NAME = "alfen"
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_PORT = 502
DEFAULT_MODBUS_ADDRESS = 200
DEFAULT_READ_SCN = False
DEFAULT_READ_SOCKET2 = False
CONF_ALFENHUB_HUB = "alfen_hub"
ATTR_STATUS_DESCRIPTION = "status_description"
ATTR_MANUFACTURER = "Alfen"
CONF_MODBUS_ADDRESS = "modbus_address"
CONF_READ_SCN = "read_scn"
CONF_READ_SOCKET2 = "read_socket_2"

VALID_TIME_S = "maxCurrentValidTime_socket_"
MAX_CURRENT_S = "maxCurrent_socket_"

SENSOR_TYPES = {
    "Name": ["Name","name" , None, None],
    "Manufacturer": ["Manufacturer","manufacturer" , None, None],
    "Modbus_table_version": ["Modbus table version","modbustableVersion" , None, None],
    "Firmware_version": ["Firmware version","firmwareVersion" , None, None],
    "Platform_type": ["Platform Type","platformType" , None, None],
    "Serial": ["Serial","serial" , None, None],
    "Current_time": ["Current time","stationTime" , None, None],
    "Last_boot": ["Last boot","lastBoot" , None, None],
    
    "Actual_max_current": ["Actual max current","actualMaxCurrent" , "A", "mdi:current-dc"],
    "Board_temp": ["Board temperature","boardTemperature" ,  "°C", None],
    "Backoffice_connected": ["Backoffice connected","backofficeConnected" , None, None],
    "Number_of_sockets": ["Number of sockets","numberOfSockets" , None, None],    
}


SOCKET1_SENSOR_TYPES = {
  "S1_Meterstate": ["S1 Meter state","socket_1_meterstate" , None, None],
  "S1_Meterage": ["S1 Meter reading age","socket_1_meterAge" ,  "s", None],
  "S1_Metertype": ["S1 Meter Type","socket_1_meterType" , None, None],
  "S1_VoltageL1N": ["S1 Voltage L1-N","socket_1_VL1-N" , "V", None],
  "S1_VoltageL2N": ["S1 Voltage L2-N","socket_1_VL2-N" , "V", None],
  "S1_VoltageL3N": ["S1 Voltage L3-N","socket_1_VL3-N" , "V", None],
  "S1_VoltageL1L2": ["S1 Voltage L1-L2","socket_1_VL1-L2" , "V", None],
  "S1_VoltageL2L3": ["S1 Voltage L2-L3","socket_1_VL2-L3" , "V", None],
  "S1_VoltageL3L1": ["S1 Voltage L3-L1","socket_1_VL3-L1" , "V", None],
  "S1_CurrN": ["S1 Current N","socket_1_currentN" , "A",  "mdi:current-ac"],
  "S1_CurrL1": ["S1 Current L1","socket_1_currentL1" , "A",  "mdi:current-ac"],
  "S1_CurrL2": ["S1 Current L2","socket_1_currentL2" , "A",  "mdi:current-ac"],
  "S1_CurrL3": ["S1 Current L3","socket_1_currentL3" , "A",  "mdi:current-ac"],
  "S1_CurrTotal": ["S1 Current Total","socket_1_currentSum" , "A",  "mdi:current-ac"],
  "S1_PowerFactorL1": ["S1 Power factor L1","socket_1_powerL1" , None, None],
  "S1_PowerFactorL2": ["S1 Power factor L2","socket_1_powerL2" , None, None],
  "S1_PowerFactorL3": ["S1 Power factor L3","socket_1_powerL3" , None, None],
  "S1_PowerFactorSum": ["S1 Power factor sum","socket_1_powerSum" ,  None, None],
  "S1_Frequency": ["S1 Frequency","socket_1_frequency" , "Hz", None],
  "S1_RealPowerL1": ["S1 Real power L1","socket_1_realPowerL1" , "W", None],
  "S1_RealPowerL2": ["S1 Real power L2","socket_1_realPowerL2" , "W", None],
  "S1_RealPowerL3": ["S1 Real power L3","socket_1_realPowerL3" , "W", None],
  "S1_RealPowerSum": ["S1 Real power sum","socket_1_realPowerSum" , "W",None],
  "S1_Apparant_Power_PhaseL1": ["S1 Apparant power L1","socket_1_apparantPowerL1" , "VA",  None],
  "S1_Apparant_Power_PhaseL2": ["S1 Apparant power L2","socket_1_apparantPowerL2" , "VA",  None],
  "S1_Apparant_Power_PhaseL3": ["S1 Apparant power L3","socket_1_apparantPowerL3" , "VA",  None],
  "S1_Apparant_Power_Sum": ["S1 Apparant power sum","socket_1_apparantPowerSum" , "VA", None],
  "S1_Reactive_Power_Phase_L1": ["S1 Reactive power L1","socket_1_reactivePowerL1" , "VAr", None],
  "S1_Reactive_Power_Phase_L2": ["S1 Reactive power L2","socket_1_reactivePowerL2" , "VAr", None],
  "S1_Reactive_Power_Phase_L3": ["S1 Reactive power L3","socket_1_reactivePowerL3" , "VAr", None],
  "S1_Reactive_Power_Sum": ["S1 Reactive power sum","socket_1_reactivePowerSum" , "VAr",None],
  "S1_Real_Enegery_Delivered_Phase_L1": ["S1 Real energy delivered L1","socket_1_realEnergyDeliveredL1" , "Wh",None],
  "S1_Real_Enegery_Delivered_Phase_L2": ["S1 Real energy delivered L2","socket_1_realEnergyDeliveredL2" , "Wh",None],
  "S1_Real_Enegery_Delivered_Phase_L3": ["S1 Real energy delivered L3","socket_1_realEnergyDeliveredL3" , "Wh",None],
  "S1_Real_Enegery_Delivered_Sum": ["S1 Real energy delivered sum","socket_1_realEnergyDeliveredSum" , "Wh",None],
  "S1_Real_Energy_Cosumed_Phase_L1": ["S1 Real energy consumed L1","socket_1_realEnergyConsumedL1" , "Wh", None],
  "S1_Real_Energy_Cosumed_Phase_L2": ["S1 Real energy consumed L2","socket_1_realEnergyConsumedL2" , "Wh", None],
  "S1_Real_Energy_Cosumed_Phase_L3": ["S1 Real energy consumed L3","socket_1_realEnergyConsumedL3" , "Wh", None],
  "S1_Real_Energy_Cosumed_Sum": ["S1 Real energy consumed sum","socket_1_realEnergyConsumedSum" , "Wh",None],
  "S1_Apparant_Energy_Phase_L1": ["S1 Apparant energy L1","socket_1_apparantEnergyL1" , "VAh",    None],
  "S1_Apparant_Energy_Phase_L2": ["S1 Apparant energy L2","socket_1_apparantEnergyL2" , "VAh",    None],
  "S1_Apparant_Energy_Phase_L3": ["S1 Apparant energy L3","socket_1_apparantEnergyL3" , "VAh",    None],
  "S1_Apparant_Energy_Sum": ["S1 Apparant energy sum","socket_1_apparantEnergySum" , "VAh",   None],
  "S1_Reactieve_Energy_Phase_L1": ["S1 Reactive energy L1","socket_1_reactiveEnergyL1" , "VAh",    None],
  "S1_Reactieve_Energy_Phase_L2": ["S1 Reactive energy L2","socket_1_reactiveEnergyL2" , "VAh",    None],
  "S1_Reactieve_Energy_Phase_L3": ["S1 Reactive energy L3","socket_1_reactiveEnergyL3" , "VAh",    None],
  "S1_Reactieve_Energy_Sum": ["S1 Reactive energy sum","socket_1_reactiveEnergySum" , "VAh",   None],
  "S1_Availability": ["S1 Availability","socket_1_available" ,  None, None],
  "S1_Mode3State": ["S1 Mode 3 State","socket_1_mode3state" ,  None, None],
  "S1_Actual_Applied_Max_Current": ["S1 Actual applied max current","socket_1_actualMaxCurrent" , "A",  "mdi:current-ac"],
  "S1_Modbus_Slave_Max_Current_Valid_Time": ["S1 Max current valid time",VALID_TIME_S+str(1) ,  "s", None],
  "S1_Modbus_Slave_Max_Current": ["S1 Max current",MAX_CURRENT_S+str(1) , "A",  "mdi:current-ac"],
  "S1_Active_Load_Balacing_Save_Current": ["S1 Active load balacing safe current","socket_1_saveCurrent" , "A",  "mdi:current-ac"],
  "S1_Slave_Setpoint_Accounted": ["S1 Received SP accounted for","socket_1_setpointAccounted" ,  None, None],
  "S1_Charging_Mode_Phases": ["S1 Charging Mode","socket_1_chargephases" , None, None],  
  "S1_Car_Charging": ["S1 Car charging","socket_1_carcharging" , None, None],  
  "S1_Car_Connected": ["S1 Car connected","socket_1_carconnected" , None, None],  
  "S1_CurrentSession": ["S1 Current session Wh", "socket_1_currentSession", "Wh", None],
  "S1_CurrentSessionDuration": ["S1 Current session duration", "socket_1_currentSessionDuration", "s", None],
}

SOCKET2_SENSOR_TYPES = {
  "S2_Meterstate": ["S2 Meter state","socket_2_meterstate" , None, None],
  "S2_Meterage": ["S2 Meter reading age","socket_2_meterAge" ,  "s", None],
  "S2_Metertype": ["S2 Meter Type","socket_2_meterType" , None, None],
  "S2_VoltageL1N": ["S2 Voltage L1-N","socket_2_VL1-N" , "V", None],
  "S2_VoltageL2N": ["S2 Voltage L2-N","socket_2_VL2-N" , "V", None],
  "S2_VoltageL3N": ["S2 Voltage L3-N","socket_2_VL3-N" , "V", None],
  "S2_VoltageL1L2": ["S2 Voltage L1-L2","socket_2_VL1-L2" , "V", None],
  "S2_VoltageL2L3": ["S2 Voltage L2-L3","socket_2_VL2-L3" , "V", None],
  "S2_VoltageL3L1": ["S2 Voltage L3-L1","socket_2_VL3-L1" , "V", None],
  "S2_CurrN": ["S2 Current N","socket_2_currentN" , "A",  "mdi:current-ac"],
  "S2_CurrL1": ["S2 Current L1","socket_2_currentL1" , "A",  "mdi:current-ac"],
  "S2_CurrL2": ["S2 Current L2","socket_2_currentL2" , "A",  "mdi:current-ac"],
  "S2_CurrL3": ["S2 Current L3","socket_2_currentL3" , "A",  "mdi:current-ac"],
  "S2_CurrTotal": ["S2 Current Total","socket_2_currentSum" , "A",  "mdi:current-ac"],
  "S2_PowerFactorL1": ["S2 Power factor L1","socket_2_powerL1" , None, None],
  "S2_PowerFactorL2": ["S2 Power factor L2","socket_2_powerL2" , None, None],
  "S2_PowerFactorL3": ["S2 Power factor L3","socket_2_powerL3" , None, None],
  "S2_PowerFactorSum": ["S2 Power factor sum","socket_2_powerSum" ,  None, None],
  "S2_Frequency": ["S2 Frequency","socket_2_frequency" , "Hz", None],
  "S2_RealPowerL1": ["S2 Real power L1","socket_2_realPowerL1" , "W", None],
  "S2_RealPowerL2": ["S2 Real power L2","socket_2_realPowerL2" , "W", None],
  "S2_RealPowerL3": ["S2 Real power L3","socket_2_realPowerL3" , "W", None],
  "S2_RealPowerSum": ["S2 Real power sum","socket_2_realPowerSum" , "W",None],
  "S2_Apparant_Power_PhaseL1": ["S2 Apparant power L1","socket_2_apparantPowerL1" , "VA",  None],
  "S2_Apparant_Power_PhaseL2": ["S2 Apparant power L2","socket_2_apparantPowerL2" , "VA",  None],
  "S2_Apparant_Power_PhaseL3": ["S2 Apparant power L3","socket_2_apparantPowerL3" , "VA",  None],
  "S2_Apparant_Power_Sum": ["S2 Apparant power sum","socket_2_apparantPowerSum" , "VA", None],
  "S2_Reactive_Power_Phase_L1": ["S2 Reactive power L1","socket_2_reactivePowerL1" , "VAr", None],
  "S2_Reactive_Power_Phase_L2": ["S2 Reactive power L2","socket_2_reactivePowerL2" , "VAr", None],
  "S2_Reactive_Power_Phase_L3": ["S2 Reactive power L3","socket_2_reactivePowerL3" , "VAr", None],
  "S2_Reactive_Power_Sum": ["S2 Reactive power sum","socket_2_reactivePowerSum" , "VAr",None],
  "S2_Real_Enegery_Delivered_Phase_L1": ["S2 Real energy delivered L1","socket_2_realEnergyDeliveredL1" , "Wh",None],
  "S2_Real_Enegery_Delivered_Phase_L2": ["S2 Real energy delivered L2","socket_2_realEnergyDeliveredL2" , "Wh",None],
  "S2_Real_Enegery_Delivered_Phase_L3": ["S2 Real energy delivered L3","socket_2_realEnergyDeliveredL3" , "Wh",None],
  "S2_Real_Enegery_Delivered_Sum": ["S2 Real energy delivered sum","socket_2_realEnergyDeliveredSum" , "Wh",None],
  "S2_Real_Energy_Cosumed_Phase_L1": ["S2 Real energy consumed L1","socket_2_realEnergyConsumedL1" , "Wh", None],
  "S2_Real_Energy_Cosumed_Phase_L2": ["S2 Real energy consumed L2","socket_2_realEnergyConsumedL2" , "Wh", None],
  "S2_Real_Energy_Cosumed_Phase_L3": ["S2 Real energy consumed L3","socket_2_realEnergyConsumedL3" , "Wh", None],
  "S2_Real_Energy_Cosumed_Sum": ["S2 Real energy consumed sum","socket_2_realEnergyConsumedSum" , "Wh",None],
  "S2_Apparant_Energy_Phase_L1": ["S2 Apparant energy L1","socket_2_apparantEnergyL1" , "VAh",    None],
  "S2_Apparant_Energy_Phase_L2": ["S2 Apparant energy L2","socket_2_apparantEnergyL2" , "VAh",    None],
  "S2_Apparant_Energy_Phase_L3": ["S2 Apparant energy L3","socket_2_apparantEnergyL3" , "VAh",    None],
  "S2_Apparant_Energy_Sum": ["S2 Apparant energy sum","socket_2_apparantEnergySum" , "VAh",   None],
  "S2_Reactieve_Energy_Phase_L1": ["S2 Reactive energy L1","socket_2_reactiveEnergyL1" , "VAh",    None],
  "S2_Reactieve_Energy_Phase_L2": ["S2 Reactive energy L2","socket_2_reactiveEnergyL2" , "VAh",    None],
  "S2_Reactieve_Energy_Phase_L3": ["S2 Reactive energy L3","socket_2_reactiveEnergyL3" , "VAh",    None],
  "S2_Reactieve_Energy_Sum": ["S2 Reactive energy sum","socket_2_reactiveEnergySum" , "VAh",   None],
  "S2_Availability": ["S2 Availability","socket_2_available" ,  None, None],
  "S2_Mode3State": ["S2 Mode 3 State","socket_2_mode3state" ,  None, None],
  "S2_Actual_Applied_Max_Current": ["S2 Actual applied max current","socket_2_actualMaxCurrent" , "A",  "mdi:current-ac"],
  "S2_Modbus_Slave_Max_Current_Valid_Time": ["S2 Max current valid time",VALID_TIME_S+str(2) ,  "s", None],
  "S2_Modbus_Slave_Max_Current": ["S2 Max current",MAX_CURRENT_S+str(2) , "A",  "mdi:current-ac"],
  "S2_Active_Load_Balacing_Save_Current": ["S2 Active load balacing safe current","socket_2_saveCurrent" , "A",  "mdi:current-ac"],
  "S2_Slave_Setpoint_Accounted": ["S2 Received SP accounted for","socket_2_setpointAccounted" ,  None, None],
  "S2_Charging_Mode_Phases": ["S2 Charging Mode","socket_2_chargephases" , None, None],  
  "S2_Car_Charging": ["S2 Car charging","socket_2_carcharging" , None, None],  
  "S2_Car_Connected": ["S2 Car connected","socket_2_carconnected" , None, None],    
  "S2_CurrentSession": ["S2 Current session Wh", "socket_2_currentSession", "Wh", None],
  "S2_CurrentSessionDuration": ["S2 Current session duration", "socket_2_currentSessionDuration", "s", None],
}

SCN_SENSOR_TYPES = {
  "SCN_Name": ["SCN Name","scnName" , None, None],
  "Number_of_scn_sockets": ["Number of SCN sockets","scnSockets" , None, None],
}


METER_TYPE = {
    0: "RTU",
    1: "TCP/IP",
    2: "UDP",
    3: "P1",
    4: "Other",
}

SCN_MAX_CURRENT_ENABLED = {
    1: "Enabled",
    0: "Disbled",    
}

BOOLEAN_EXPLAINED = {
    1: True,
    0: False,    
}

METER_STATE_MODES = {    
    0: "Unknown",    
    1: "Initialised",
    2: "Updated",
    3: "Initialised, Updated",
    4: "Warning",
    5: "Initialised, Warning",
    6: "Updated, Warning",
    7: "Initialised, Updated, Warning",
    8: "Error",    
    9: "Initialised, Error",
    10: "Updated, Error",
    11: "Initialised, Updated, Error",
    12: "Warning, Error",
    13: "Initialised, Warning, Error",
    14: "Updated, Warning, Error",    
    15: "Initialised, Updated, Warning, Error",    
}

AVAILABILITY_MODES = {
    1: "Operative",
    0: "Inoperative",    
}

CONTROL_PHASE_MODES = {
    1: "1 Phase",
    3: "3 Phases",    
}

CONTROL_PHASE = [
    ["Usable phases", "usephases_S", 1215, CONTROL_PHASE_MODES],
]


CONTROL_SLAVE_MAX_CURRENT = [
    ["Max Current Limit S", MAX_CURRENT_S, 1210, "f", {"min": 0, "max": 32, "unit": "A", "mode": "slider", "step": 0.1}]
]
