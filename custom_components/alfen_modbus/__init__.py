"""The Alfen Modbus Integration."""
import asyncio
import logging
import operator
import threading
from datetime import datetime, timedelta  
from dateutil.tz import tzoffset
from typing import Optional

import voluptuous as vol
from pymodbus.client import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from .const import (
    DOMAIN,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_MODBUS_ADDRESS,
    CONF_MODBUS_ADDRESS,
    CONF_READ_SCN,
    CONF_READ_SOCKET2,
    DEFAULT_READ_SCN,
    DEFAULT_READ_SOCKET2,
    VALID_TIME_S,
    MAX_CURRENT_S,
)

_LOGGER = logging.getLogger(__name__)

ALFEN_MODBUS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.string,
        vol.Optional(
            CONF_MODBUS_ADDRESS, default=DEFAULT_MODBUS_ADDRESS
        ): cv.positive_int,
        vol.Optional(CONF_READ_SCN, default=DEFAULT_READ_SCN): cv.boolean,
        vol.Optional(CONF_READ_SOCKET2, default=DEFAULT_READ_SOCKET2): cv.boolean,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({cv.slug: ALFEN_MODBUS_SCHEMA})}, extra=vol.ALLOW_EXTRA
)

PLATFORMS = ["number", "select", "sensor"]


async def async_setup(hass, config):
    """Set up the Alfen modbus component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a alfen mobus."""
    host = entry.data[CONF_HOST]
    name = entry.data[CONF_NAME]
    port = entry.data[CONF_PORT]
    address = entry.data.get(CONF_MODBUS_ADDRESS, 1)
    scan_interval = entry.data[CONF_SCAN_INTERVAL]
    read_scn = entry.data.get(CONF_READ_SCN, False)
    read_socket2 = entry.data.get(CONF_READ_SOCKET2, False)

    _LOGGER.debug("Setup %s.%s", DOMAIN, name)

    hub = AlfenModbusHub(
        hass,
        name,
        host,
        port,
        address,
        scan_interval,
        read_scn,
        read_socket2
    )
    """Register the hub."""
    hass.data[DOMAIN][name] = {"hub": hub}

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    return True


async def async_unload_entry(hass, entry):
    """Unload Alfen mobus entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if not unload_ok:
        return False

    hass.data[DOMAIN].pop(entry.data["name"])
    return True


def validate(value, comparison, against):
    ops = {
        ">": operator.gt,
        "<": operator.lt,
        ">=": operator.ge,
        "<=": operator.le,
        "==": operator.eq,
        "!=": operator.ne,
    }
    if not ops[comparison](value, against):
        raise ValueError(f"Value {value} failed validation ({comparison}{against})")
    return value


class AlfenModbusHub:
    """Thread safe wrapper class for pymodbus."""

    def __init__(
        self,
        hass,
        name,
        host,
        port,
        address,
        scan_interval,
        read_scn=False,
        read_socket_2=False
    ):
        """Initialize the Modbus hub."""
        self._hass = hass
        self._client = ModbusTcpClient(host=host, port=port)
        self._lock = threading.Lock()
        self._name = name
        self._address = address
        self.read_scn = read_scn
        self.read_socket_2 = read_socket_2
        self._refreshInterval = scan_interval
        self._scan_interval = timedelta(seconds=scan_interval)
        self._unsub_interval_method = None
        self._sensors = []    
        self._inputs = []    
        self.data = {}

    @callback
    def async_add_alfen_sensor(self, update_callback, refresh_callback = None):
        """Listen for data updates."""
        # This is the first sensor, set up interval.
        if not self._sensors:
            self.connect()
            self._unsub_interval_method = async_track_time_interval(
                self._hass, self.async_refresh_modbus_data, self._scan_interval
            )

        self._sensors.append(update_callback)
        if refresh_callback is not None:
           self._inputs.append(refresh_callback)

    @callback
    def async_remove_alfen_sensor(self, update_callback, refresh_callback = None):
        """Remove data update."""
        self._sensors.remove(update_callback)
        if refresh_callback is not None:
           self._inputs.remove(refresh_callback)
        if not self._sensors:
            """stop the interval timer upon removal of last sensor"""
            self._unsub_interval_method()
            self._unsub_interval_method = None
            self.close()



    async def async_refresh_modbus_data(self, _now: Optional[int] = None) -> None:
        """Time to update."""
        if not self._sensors:
            return

        try:
            update_result = self.read_modbus_data()
        except Exception as e:
            _LOGGER.exception("Error reading modbus data")
            update_result = False

        if update_result:
            for update_callback in self._sensors:
                update_callback()
            self.refresh_max_current()

    @property
    def name(self):
        """Return the name of this hub."""
        return self._name

    def close(self):
        """Disconnect client."""
        with self._lock:
            self._client.close()

    def connect(self):
        """Connect client."""
        with self._lock:
            self._client.connect()

    @property
    def has_socket_2(self):
        """Return true if a meter is available"""
        return self.read_socket_2

    @property
    def has_scn(self):
        """Return true if a battery is available"""
        return self.read_scn

    def read_holding_registers(self, unit, address, count):
        """Read holding registers."""
        with self._lock:
            return self._client.read_holding_registers(
                address=address, count=count, slave=unit
            )

    def write_registers(self, unit, address, payload):
        """Write registers."""
        with self._lock:
            return self._client.write_registers(
                address=address, values=payload, slave=unit
            )
            
    def refresh_max_current(self):
        if int(self.data[VALID_TIME_S+"1"]) < self._refreshInterval+10 or (self.has_socket_2 and int(self.data[VALID_TIME_S+"2"]) < self._refreshInterval+10):
            for update_value in self._inputs:
                update_value()
            
            

    def read_modbus_data(self):
        return (
            self.read_modbus_data_product()
            and self.read_modbus_data_station()
            and self.read_modbus_data_scn()
            and self.read_modbus_data_socket(1)
            and self.read_modbus_data_socket(2)            
        )

    def decode_string(self, decoder,length):
        s = decoder.decode_string(length*2)  # get 32 char string
        s = s.partition(b"\0")[0]  # omit NULL terminators
        s = s.decode("utf-8")  # decode UTF-8
        return str(s)

    def read_modbus_data_station(self):
        status_data = self.read_holding_registers(self._address,1100,6)
        if status_data.isError():
            return False
        decoder = BinaryPayloadDecoder.fromRegisters(
            status_data.registers, byteorder=Endian.BIG
        )
        self.data["actualMaxCurrent"] =  round(decoder.decode_32bit_float(),2)
        self.data["boardTemperature"] =  round(decoder.decode_32bit_float(),2)
        self.data["backofficeConnected"] = decoder.decode_16bit_uint()
        self.data["numberOfSockets"] = decoder.decode_16bit_uint()
        return True
        
    def read_modbus_data_scn(self):
        if(self.has_scn):
            status_data = self.read_holding_registers(self._address,1400,32)
            if status_data.isError():
                return False
            decoder = BinaryPayloadDecoder.fromRegisters(
                status_data.registers, byteorder=Endian.BIG
            )
            self.data["scnName"] = self.decode_string(decoder,4)
            self.data["scnSockets"] = decoder.decode_16bit_int()
            #todo, Smart charging network registers
        return True
        
    def read_modbus_data_socket(self,socket):
        if((socket == 1) or (socket == 2 and self.has_socket_2 and self.data["numberOfSockets"] >= 2)):
            energy_data = self.read_holding_registers(socket,300,125)
            if energy_data.isError():
                return False
            decoder = BinaryPayloadDecoder.fromRegisters(
                energy_data.registers, byteorder=Endian.BIG
            )
            self.data["socket_"+str(socket)+"_meterstate"] = decoder.decode_16bit_uint()
            self.data["socket_"+str(socket)+"_meterAge"] = decoder.decode_64bit_uint()
            self.data["socket_"+str(socket)+"_meterType"] = decoder.decode_16bit_uint()
            
            self.data["socket_"+str(socket)+"_VL1-N"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_VL2-N"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_VL3-N"] =  round(decoder.decode_32bit_float(),2)
            
            self.data["socket_"+str(socket)+"_VL1-L2"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_VL2-L3"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_VL3-L1"] =  round(decoder.decode_32bit_float(),2)
            
            self.data["socket_"+str(socket)+"_currentN"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_currentL1"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_currentL2"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_currentL3"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_currentSum"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_powerL1"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_powerL2"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_powerL3"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_powerSum"] =  round(decoder.decode_32bit_float(),2)
            
            self.data["socket_"+str(socket)+"_frequency"] =  round(decoder.decode_32bit_float(),2)
            
            self.data["socket_"+str(socket)+"_realPowerL1"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_realPowerL2"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_realPowerL3"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_realPowerSum"] =  round(decoder.decode_32bit_float(),2)        
            self.data["socket_"+str(socket)+"_apparantPowerL1"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_apparantPowerL2"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_apparantPowerL3"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_apparantPowerSum"] =  round(decoder.decode_32bit_float(),2)        
                    
            self.data["socket_"+str(socket)+"_reactivePowerL1"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_reactivePowerL2"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_reactivePowerL3"] =  round(decoder.decode_32bit_float(),2)
            self.data["socket_"+str(socket)+"_reactivePowerSum"] =  round(decoder.decode_32bit_float(),2)        

            self.data["socket_"+str(socket)+"_realEnergyDeliveredL1"] =  round(decoder.decode_64bit_float(),2)
            self.data["socket_"+str(socket)+"_realEnergyDeliveredL2"] =  round(decoder.decode_64bit_float(),2)
            self.data["socket_"+str(socket)+"_realEnergyDeliveredL3"] =  round(decoder.decode_64bit_float(),2)
            self.data["socket_"+str(socket)+"_realEnergyDeliveredSum"] =  round(decoder.decode_64bit_float(),2)        
            self.data["socket_"+str(socket)+"_realEnergyConsumedL1"] =  round(decoder.decode_64bit_float(),2)
            self.data["socket_"+str(socket)+"_realEnergyConsumedL2"] =  round(decoder.decode_64bit_float(),2)
            self.data["socket_"+str(socket)+"_realEnergyConsumedL3"] =  round(decoder.decode_64bit_float(),2)
            self.data["socket_"+str(socket)+"_realEnergyConsumedSum"] =  round(decoder.decode_64bit_float(),2)        
            self.data["socket_"+str(socket)+"_apparantEnergyL1"] =  round(decoder.decode_64bit_float(),2)
            self.data["socket_"+str(socket)+"_apparantEnergyL2"] =  round(decoder.decode_64bit_float(),2)
            self.data["socket_"+str(socket)+"_apparantEnergyL3"] =  round(decoder.decode_64bit_float(),2)
            self.data["socket_"+str(socket)+"_apparantEnergySum"] =  round(decoder.decode_64bit_float(),2)        
                    
            self.data["socket_"+str(socket)+"_reactiveEnergyL1"] =  round(decoder.decode_64bit_float(),2)
            self.data["socket_"+str(socket)+"_reactiveEnergyL2"] =  round(decoder.decode_64bit_float(),2)
            self.data["socket_"+str(socket)+"_reactiveEnergyL3"] =  round(decoder.decode_64bit_float(),2)
            self.data["socket_"+str(socket)+"_reactiveEnergySum"] = 0# round(decoder.decode_64bit_float(),2)        
                                            
                            
            status_data = self.read_holding_registers(socket,1200,16)
            if status_data.isError():
                return False
            decoder = BinaryPayloadDecoder.fromRegisters(
                status_data.registers, byteorder=Endian.BIG
            )
            self.data["socket_"+str(socket)+"_available"] = decoder.decode_16bit_uint()        
            self.data["socket_"+str(socket)+"_mode3state"] = self.decode_string(decoder,5)      
            self.data["socket_"+str(socket)+"_actualMaxCurrent"] =  round(decoder.decode_32bit_float(),2)        
            self.data[VALID_TIME_S+str(socket)] = decoder.decode_32bit_uint()        
            self.data[MAX_CURRENT_S+str(socket)] =  round(decoder.decode_32bit_float(),2)        
            self.data["socket_"+str(socket)+"_saveCurrent"] =  round(decoder.decode_32bit_float(),2)        
            self.data["socket_"+str(socket)+"_setpointAccounted"] = decoder.decode_16bit_uint()        
            self.data["socket_"+str(socket)+"_chargephases"] = decoder.decode_16bit_uint()     
            
            if self.data["socket_"+str(socket)+"_mode3state"] in ["A","E","F"]:
                self.data["socket_"+str(socket)+"_carconnected"] = 0             
            else:
                self.data["socket_"+str(socket)+"_carconnected"] = 1          
            
            if self.data["socket_"+str(socket)+"_mode3state"] not in ["C2","D2"]:
                self.data["socket_"+str(socket)+"_carcharging"] = 0                    
            else:
                if "socket_"+str(socket)+"_carcharging" not in self.data or self.data["socket_"+str(socket)+"_carcharging"] == 0:                    
                    self.data["socket_"+str(socket)+"_chargingStartWh"] = self.data["socket_"+str(socket)+"_realEnergyDeliveredSum"]
                    self.data["socket_"+str(socket)+"_chargingStart"] = self.data["stationTime"]
                self.data["socket_"+str(socket)+"_carcharging"] = 1
                
            if "socket_"+str(socket)+"_chargingStartWh" in self.data and "socket_"+str(socket)+"_chargingStart" in self.data and self.data["socket_"+str(socket)+"_carcharging"] == 1:     
                self.data["socket_"+str(socket)+"_currentSession"] = self.data["socket_"+str(socket)+"_realEnergyDeliveredSum"] - self.data["socket_"+str(socket)+"_chargingStartWh"]               
                self.data["socket_"+str(socket)+"_currentSessionDuration"] = self.data["stationTime"] - self.data["socket_"+str(socket)+"_chargingStart"]
        return True           
        
        
    def read_modbus_data_product(self):
        identification_data = self.read_holding_registers(self._address,100,79)
        if identification_data.isError():
            return False
        decoder = BinaryPayloadDecoder.fromRegisters(
            identification_data.registers, byteorder=Endian.BIG
        )
         
        self.data["name"] = self.decode_string(decoder,17)
        self.data["manufacturer"] = self.decode_string(decoder,5)
        self.data["modbustableVersion"] = decoder.decode_16bit_int()
        self.data["firmwareVersion"] =self.decode_string(decoder,17)
        self.data["platformType"] =self.decode_string(decoder,17)        
        self.data["serial"] =self.decode_string(decoder,11)
        
        year = decoder.decode_16bit_int()
        month = decoder.decode_16bit_int()
        day = decoder.decode_16bit_int()
        hour = decoder.decode_16bit_int()   
        minute = decoder.decode_16bit_int()
        second = decoder.decode_16bit_int()
        uptime = decoder.decode_64bit_uint()
        utcoffset = decoder.decode_16bit_int()
        
        self.data["stationTime"] = datetime(year,month,day,hour,minute,second,tzinfo=tzoffset("",offset=utcoffset*60))       
        lastBoot = self.data["stationTime"] - timedelta(milliseconds=uptime)
        self.data["lastBoot"] = lastBoot - timedelta(microseconds=lastBoot.microsecond)
        return True
