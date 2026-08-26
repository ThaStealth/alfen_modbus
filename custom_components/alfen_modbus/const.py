DOMAIN = "alfen_modbus"
DEFAULT_MANUFACTURER = "Alfen"
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
    "Name": ["name", "name", None, None],
    "Manufacturer": ["manufacturer", "manufacturer", None, None],
    "Modbus_table_version": ["modbus_table_version", "modbustableVersion", None, None],
    "Firmware_version": ["firmware_version", "firmwareVersion", None, None],
    "Platform_type": ["platform_type", "platformType", None, None],
    "Serial": ["serial", "serial", None, None],
    "Current_time": ["current_time", "stationTime", None, None],
    "Last_boot": ["last_boot", "lastBoot", None, None],
    "Actual_max_current": ["actual_max_current", "actualMaxCurrent", "A", "mdi:current-dc"],
    "Board_temp": ["board_temperature", "boardTemperature", "°C", None],
    "Backoffice_connected": ["backoffice_connected", "backofficeConnected", None, None],
    "Number_of_sockets": ["number_of_sockets", "numberOfSockets", None, None],
}


SOCKET_SENSOR_TYPES = {
    "S1_Meterstate": ["meter_state", "socket_{socket}_meterstate", None, None],
    "S1_Meterage": ["meter_reading_age", "socket_{socket}_meterAge", "s", None],
    "S1_Metertype": ["meter_type", "socket_{socket}_meterType", None, None],
    "S1_VoltageL1N": ["voltage_l1_n", "socket_{socket}_VL1-N", "V", None],
    "S1_VoltageL2N": ["voltage_l2_n", "socket_{socket}_VL2-N", "V", None],
    "S1_VoltageL3N": ["voltage_l3_n", "socket_{socket}_VL3-N", "V", None],
    "S1_VoltageL1L2": ["voltage_l1_l2", "socket_{socket}_VL1-L2", "V", None],
    "S1_VoltageL2L3": ["voltage_l2_l3", "socket_{socket}_VL2-L3", "V", None],
    "S1_VoltageL3L1": ["voltage_l3_l1", "socket_{socket}_VL3-L1", "V", None],
    "S1_CurrN": ["current_n", "socket_{socket}_currentN", "A", "mdi:current-ac"],
    "S1_CurrL1": ["current_l1", "socket_{socket}_currentL1", "A", "mdi:current-ac"],
    "S1_CurrL2": ["current_l2", "socket_{socket}_currentL2", "A", "mdi:current-ac"],
    "S1_CurrL3": ["current_l3", "socket_{socket}_currentL3", "A", "mdi:current-ac"],
    "S1_CurrTotal": ["current_total", "socket_{socket}_currentSum", "A", "mdi:current-ac"],
    "S1_PowerFactorL1": ["power_factor_l1", "socket_{socket}_powerL1", None, None],
    "S1_PowerFactorL2": ["power_factor_l2", "socket_{socket}_powerL2", None, None],
    "S1_PowerFactorL3": ["power_factor_l3", "socket_{socket}_powerL3", None, None],
    "S1_PowerFactorSum": ["power_factor_sum", "socket_{socket}_powerSum", None, None],
    "S1_Frequency": ["frequency", "socket_{socket}_frequency", "Hz", None],
    "S1_RealPowerL1": ["real_power_l1", "socket_{socket}_realPowerL1", "W", None],
    "S1_RealPowerL2": ["real_power_l2", "socket_{socket}_realPowerL2", "W", None],
    "S1_RealPowerL3": ["real_power_l3", "socket_{socket}_realPowerL3", "W", None],
    "S1_RealPowerSum": ["real_power_sum", "socket_{socket}_realPowerSum", "W", None],
    "S1_Apparant_Power_PhaseL1": ["apparent_power_l1", "socket_{socket}_apparantPowerL1", "VA", None],
    "S1_Apparant_Power_PhaseL2": ["apparent_power_l2", "socket_{socket}_apparantPowerL2", "VA", None],
    "S1_Apparant_Power_PhaseL3": ["apparent_power_l3", "socket_{socket}_apparantPowerL3", "VA", None],
    "S1_Apparant_Power_Sum": ["apparent_power_sum", "socket_{socket}_apparantPowerSum", "VA", None],
    "S1_Reactive_Power_Phase_L1": ["reactive_power_l1", "socket_{socket}_reactivePowerL1", "VAr", None],
    "S1_Reactive_Power_Phase_L2": ["reactive_power_l2", "socket_{socket}_reactivePowerL2", "VAr", None],
    "S1_Reactive_Power_Phase_L3": ["reactive_power_l3", "socket_{socket}_reactivePowerL3", "VAr", None],
    "S1_Reactive_Power_Sum": ["reactive_power_sum", "socket_{socket}_reactivePowerSum", "VAr", None],
    "S1_Real_Enegery_Delivered_Phase_L1": ["real_energy_delivered_l1", "socket_{socket}_realEnergyDeliveredL1", "Wh", None],
    "S1_Real_Enegery_Delivered_Phase_L2": ["real_energy_delivered_l2", "socket_{socket}_realEnergyDeliveredL2", "Wh", None],
    "S1_Real_Enegery_Delivered_Phase_L3": ["real_energy_delivered_l3", "socket_{socket}_realEnergyDeliveredL3", "Wh", None],
    "S1_Real_Enegery_Delivered_Sum": ["real_energy_delivered_sum", "socket_{socket}_realEnergyDeliveredSum", "Wh", None],
    "S1_Real_Energy_Cosumed_Phase_L1": ["real_energy_consumed_l1", "socket_{socket}_realEnergyConsumedL1", "Wh", None],
    "S1_Real_Energy_Cosumed_Phase_L2": ["real_energy_consumed_l2", "socket_{socket}_realEnergyConsumedL2", "Wh", None],
    "S1_Real_Energy_Cosumed_Phase_L3": ["real_energy_consumed_l3", "socket_{socket}_realEnergyConsumedL3", "Wh", None],
    "S1_Real_Energy_Cosumed_Sum": ["real_energy_consumed_sum", "socket_{socket}_realEnergyConsumedSum", "Wh", None],
    "S1_Apparant_Energy_Phase_L1": ["apparent_energy_l1", "socket_{socket}_apparantEnergyL1", "VAh", None],
    "S1_Apparant_Energy_Phase_L2": ["apparent_energy_l2", "socket_{socket}_apparantEnergyL2", "VAh", None],
    "S1_Apparant_Energy_Phase_L3": ["apparent_energy_l3", "socket_{socket}_apparantEnergyL3", "VAh", None],
    "S1_Apparant_Energy_Sum": ["apparent_energy_sum", "socket_{socket}_apparantEnergySum", "VAh", None],
    "S1_Reactieve_Energy_Phase_L1": ["reactive_energy_l1", "socket_{socket}_reactiveEnergyL1", "VAh", None],
    "S1_Reactieve_Energy_Phase_L2": ["reactive_energy_l2", "socket_{socket}_reactiveEnergyL2", "VAh", None],
    "S1_Reactieve_Energy_Phase_L3": ["reactive_energy_l3", "socket_{socket}_reactiveEnergyL3", "VAh", None],
    "S1_Reactieve_Energy_Sum": ["reactive_energy_sum", "socket_{socket}_reactiveEnergySum", "VAh", None],
    "S1_Availability": ["availability", "socket_{socket}_available", None, None],
    "S1_Mode3State": ["mode_3_state", "socket_{socket}_mode3state", None, None],
    "S1_Actual_Applied_Max_Current": ["actual_applied_max_current", "socket_{socket}_actualMaxCurrent", "A", "mdi:current-ac"],
    "S1_Modbus_Slave_Max_Current_Valid_Time": ["max_current_valid_time", "maxCurrentValidTime_socket_{socket}", "s", None],
    "S1_Modbus_Slave_Max_Current": ["max_current", "maxCurrent_socket_{socket}", "A", "mdi:current-ac"],
    "S1_Active_Load_Balacing_Save_Current": ["active_load_balancing_safe_current", "socket_{socket}_saveCurrent", "A", "mdi:current-ac"],
    "S1_Slave_Setpoint_Accounted": ["received_sp_accounted_for", "socket_{socket}_setpointAccounted", None, None],
    "S1_Charging_Mode_Phases": ["charging_mode", "socket_{socket}_chargephases", None, None],
    "S1_Car_Charging": ["car_charging", "socket_{socket}_carcharging", None, None],
    "S1_Car_Connected": ["car_connected", "socket_{socket}_carconnected", None, None],
    "S1_CurrentSession": ["current_session_wh", "socket_{socket}_currentSession", "Wh", None],
    "S1_CurrentSessionDuration": ["current_session_duration", "socket_{socket}_currentSessionDuration", "s", None],
}

SCN_SENSOR_TYPES = {
    "SCN_Name": ["scn_name", "scnName", None, None],
    "Number_of_scn_sockets": ["number_of_scn_sockets", "scnSockets", None, None],
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

# Sensor keys whose value comes from BOOLEAN_EXPLAINED and should be
# rendered as a localized "on"/"off" enum state instead of a raw
# Python boolean. Their translation_key already comes from
# SENSOR_TYPES/SOCKET_SENSOR_TYPES.
ENUM_SENSOR_KEYS = {
    "backofficeConnected",
    "socket_1_setpointAccounted",
    "socket_2_setpointAccounted",
    "socket_1_carconnected",
    "socket_2_carconnected",
    "socket_1_carcharging",
    "socket_2_carcharging",
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
    ["usable_phases", "usephases_S", 1215, CONTROL_PHASE_MODES],
]


CONTROL_SLAVE_MAX_CURRENT = [
    ["max_current_limit", MAX_CURRENT_S, 1210, "f", {"min": 0, "max": 32, "unit": "A", "mode": "slider", "step": 0.1}]
]
