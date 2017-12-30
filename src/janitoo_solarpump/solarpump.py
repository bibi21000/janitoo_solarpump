# -*- coding: utf-8 -*-
"""The Raspberry solarpump

"""

__license__ = """
    This file is part of Janitoo.

    Janitoo is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Janitoo is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Janitoo. If not, see <http://www.gnu.org/licenses/>.

"""
__author__ = 'Sébastien GALLET aka bibi21000'
__email__ = 'bibi21000@gmail.com'
__copyright__ = "Copyright © 2013-2014-2015-2016 Sébastien GALLET aka bibi21000"

import logging
logger = logging.getLogger(__name__)
import os, sys
import threading
import datetime

from janitoo.fsm import HierarchicalMachine as Machine
from janitoo.thread import JNTBusThread, BaseThread
from janitoo.options import get_option_autostart
from janitoo.utils import HADD
from janitoo.node import JNTNode
from janitoo.value import JNTValue
from janitoo.component import JNTComponent

from janitoo_factory.buses.fsm import JNTFsmBus
from janitoo_factory.threads.http import BasicResourceComponent

from janitoo_raspberry_dht.dht import DHTComponent
from janitoo_raspberry_gpio.gpio import GpioBus, OutputComponent as GpioOut, InputComponent as GpioIn
from janitoo_raspberry_i2c.bus_i2c import I2CBus
from janitoo_raspberry_i2c_ds1307.ds1307 import DS1307Component
from janitoo_raspberry_i2c_ads1x15.ads import ADSComponent as Ads1x15Component
from janitoo_raspberry_1wire.bus_1wire import OnewireBus
from janitoo_raspberry_1wire.components import DS18B20
from janitoo_hostsensor_raspberry.component import HardwareCpu

##############################################################
#Check that we are in sync with the official command classes
#Must be implemented for non-regression
from janitoo.classes import COMMAND_DESC

COMMAND_WEB_CONTROLLER = 0x1030
COMMAND_WEB_RESOURCE = 0x1031
COMMAND_DOC_RESOURCE = 0x1032

assert(COMMAND_DESC[COMMAND_WEB_CONTROLLER] == 'COMMAND_WEB_CONTROLLER')
assert(COMMAND_DESC[COMMAND_WEB_RESOURCE] == 'COMMAND_WEB_RESOURCE')
assert(COMMAND_DESC[COMMAND_DOC_RESOURCE] == 'COMMAND_DOC_RESOURCE')
##############################################################

from janitoo_solarpump import OID

def make_ambiance(**kwargs):
    return AmbianceComponent(**kwargs)

def make_cpu(**kwargs):
    return CpuComponent(**kwargs)

def make_ads(**kwargs):
    return AdsComponent(**kwargs)

def make_clock(**kwargs):
    return ClockComponent(**kwargs)

def make_temperature(**kwargs):
    return TemperatureComponent(**kwargs)

def make_output(**kwargs):
    return OutputComponent(**kwargs)
    
def make_input(**kwargs):
    return InputComponent(**kwargs)

def make_led(**kwargs):
    return LedComponent(**kwargs)

def make_http_resource(**kwargs):
    return HttpResourceComponent(**kwargs)

#~ def make_pump(**kwargs):
    #~ return PumpComponent(**kwargs)

#~ def make_pir(**kwargs):
    #~ return PirComponent(**kwargs)

#~ def make_proximity(**kwargs):
    #~ return ProximityComponent(**kwargs)


class SolarpumpBus(JNTFsmBus):
    """A bus to manage Solarpump
    """

    states = [
       'booting',
       'sleeping',
       'charging',
       'freezing',
       { 'name': 'running',
         'children': ['pumping', 'waiting'],
       },
    ]
    """The solarpump states :
        - sleeping : the power is very low, we do not poll sensors again (except the battery ones, 
        - charging : power is low. We can poll sensors again.
        - running : power is ok. We may pump
            - pumping : the pump is on !!!
            - freezing : stop pumping !!!
            - waiting : waiting for water
    """

    transitions = [
        { 'trigger': 'boot',
            'source': 'booting',
            'dest': 'sleeping',
            'conditions': 'condition_booting',
        },
        { 'trigger': 'sleep',
            'source': '*',
            'dest': 'sleeping',
            'conditions': 'condition_sleeping',
        },
        { 'trigger': 'charge',
            'source': '*',
            'dest': 'charging',
            'conditions': 'condition_running',
        },
        { 'trigger': 'freeze',
            'source': '*',
            'dest': 'freezing',
            'conditions': 'condition_sleeping',
        },
        { 'trigger': 'pump',
            'source': 'running',
            'dest': 'running_pumping',
            'conditions': 'condition_running',
        },
        { 'trigger': 'run',
            'source': 'charging',
            'dest': 'running',
            'conditions': 'condition_running',
        },
        { 'trigger': 'wait',
            'source': 'running',
            'dest': 'running_waiting',
            'conditions': 'condition_running',
        },
    ]

    def __init__(self, **kwargs):
        """
        """
        JNTFsmBus.__init__(self, **kwargs)
        self.buses = {}
        self.buses['gpiobus'] = GpioBus(masters=[self], **kwargs)
        self.buses['1wire'] = OnewireBus(masters=[self], **kwargs)
        self.buses['i2c'] = I2CBus(masters=[self], **kwargs)
        self.check_timer = None
        uuid="{:s}_timer_delay".format(OID)
        self.values[uuid] = self.value_factory['config_integer'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The delay between 2 checks',
            label='Timer.',
            default=10,
        )
        uuid="{:s}_temperature_freeze".format(OID)
        self.values[uuid] = self.value_factory['config_float'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The feezing temperature.',
            label='Temp Freeze',
            default=0,
        )

        uuid="{:s}_temperature_min".format(OID)
        self.values[uuid] = self.value_factory['config_float'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The minimum temperature to restart pumping.',
            label='Temp Min',
            default=0,
        )

        uuid="{:s}_battery_critical".format(OID)
        self.values[uuid] = self.value_factory['config_float'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The critical level for battery.',
            label='batt crit',
            default=11.6,
        )

        uuid="{:s}_battery_min".format(OID)
        self.values[uuid] = self.value_factory['config_float'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The minimal level for battery.',
            label='batt crit',
            default=12.5,
        )

        uuid="{:s}_state".format(OID)
        self.values[uuid] = self.value_factory['sensor_integer'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The state of the system : -3 booting -2 sleeping, -1 charging, 0 freezing, 1 waiting, 2 pumping.',
            label='state',
            default=-3,
        )
        
        self.thread_start_motor = None

    @property
    def sleeping_sensors(self):
        """The sensors we will poll
        """
        return self.booting_sensors.union( set( [
            self.nodeman.find_value('temperature', 'temperature'),
            self.nodeman.find_value('temp_battery', 'temperature'),
            self.nodeman.find_value('led', 'state'),
            self.nodeman.find_value('ambiancein', 'temperature'),
            self.nodeman.find_value('ambianceout', 'temperature'),
        ]))

    @property
    def running_sensors(self):
        """The sensors we will poll
        """
        water_sensors = []
        if self.nodeman.find_value('level1', 'state') is not None:
            water_sensors = [
                self.nodeman.find_value('level1', 'state'),
                self.nodeman.find_value('level2', 'state'),
            ]
        return self.sleeping_sensors.union( set( water_sensors + [
            self.nodeman.find_value('ambiancein', 'humidity'),
            self.nodeman.find_value('ambianceout', 'humidity'),
            self.nodeman.find_value('cpu', 'temperature'),
            self.nodeman.find_value('cpu', 'voltage'),
            self.nodeman.find_value('cpu', 'frequency'),
            self.nodeman.find_value('pump', 'state'),
            self.nodeman.find_value('inverter', 'state'),
        ]))

    @property
    def booting_sensors(self):
        """The sensors we will poll at boot
        """
        return set([
            self.nodeman.find_value('battery', 'voltage'),
            self.nodeman.find_value('solar', 'voltage'),
        ])

    def condition_booting(self):
        """Return True if all sensors are available
        """
        polled_sensors = self.booting_sensors
        logger.debug("[%s] - condition_booting sensors : %s", self.__class__.__name__, polled_sensors)
        return all(v is not None for v in polled_sensors)

    def condition_running(self):
        """Return True if all sensors are available
        """
        polled_sensors = self.running_sensors
        logger.debug("[%s] - condition_running sensors : %s", self.__class__.__name__, polled_sensors)
        return all(v is not None for v in polled_sensors)

    def condition_sleeping(self):
        """Return True if all sensors are available
        """
        polled_sensors = self.sleeping_sensors
        logger.debug("[%s] - condition_sleeping sensors : %s", self.__class__.__name__, polled_sensors)
        return all(v is not None for v in polled_sensors)

    def on_enter_sleeping(self):
        """
        """
        logger.debug("[%s] - on_enter_sleeping", self.__class__.__name__)
        self.bus_acquire()
        try:
            self.stop_check()
            self.nodeman.remove_polls(self.running_sensors - self.sleeping_sensors)
            self.nodeman.add_polls(self.sleeping_sensors, slow_start=True, overwrite=False)
            self.nodeman.find_value('led', 'blink').data = 'off'
        except Exception:
            logger.exception("[%s] - Error in on_enter_sleeping", self.__class__.__name__)
        finally:
            self.bus_release()

    def on_enter_booting(self):
        """
        """
        logger.info("[%s] - on_enter_booting", self.__class__.__name__)
        self.bus_acquire()
        try:
            self.stop_check()
            self.nodeman.remove_polls(self.running_sensors - self.sleeping_sensors)
            self.nodeman.add_polls(self.sleeping_sensors, slow_start=True, overwrite=False)
            self.nodeman.find_value('led', 'blink').data = 'off'
            self.get_bus_value('state').data = -3
        except Exception:
            logger.exception("[%s] - Error in on_enter_booting", self.__class__.__name__)
        finally:
            self.bus_release()

    def on_enter_charging(self):
        """
        """
        logger.info("[%s] - on_enter_charging", self.__class__.__name__)
        self.bus_acquire()
        try:
            self.nodeman.add_polls(self.sleeping_sensors, slow_start=True, overwrite=False)
            self.nodeman.find_value('led', 'blink').data = 'off'
            self.get_bus_value('state').data = -1
        except Exception:
            logger.exception("[%s] - Error in on_enter_charging", self.__class__.__name__)
        finally:
            self.bus_release()
        try:
            if self.check_timer is None and self.is_started:
                self.check_timer = threading.Timer(self.get_bus_value('timer_delay').data, self.on_check)
                self.check_timer.start()
        except Exception:
            logger.exception("[%s] - Error in on_enter_charging", self.__class__.__name__)

    def on_enter_running(self):
        """
        """
        logger.info("[%s] - on_enter_running", self.__class__.__name__)
        self.bus_acquire()
        try:
            self.nodeman.find_value('led', 'blink').data = 'heartbeat'
            self.nodeman.add_polls(self.running_sensors, slow_start=True, overwrite=False)
        except Exception:
            logger.exception("[%s] - Error in on_enter_running", self.__class__.__name__)
        finally:
            self.bus_release()

    def on_enter_freezing(self):
        """
        """
        logger.info("[%s] - on_enter_freezing", self.__class__.__name__)
        self.bus_acquire()
        try:
            self.nodeman.find_value('led', 'blink').data = 'notify'
            self.get_bus_value('state').data = -1
        except Exception:
            logger.exception("[%s] - Error in on_enter_freezing", self.__class__.__name__)
        finally:
            self.bus_release()

    def on_enter_running_pumping(self):
        """ Start the pump system
        """
        logger.info("[%s] - on_enter_running_pumping", self.__class__.__name__)
        self.bus_acquire()
        try:
            if self.thread_start_motor is not None:
                self.thread_start_motor.cancel()
                self.thread_start_motor = None
            self.nodeman.find_value('led', 'blink').data = 'info1'
            self.start_inverter()
            self.thread_start_motor = threading.Timer(5, self.start_pump)
            self.thread_start_motor.start()
            self.get_bus_value('state').data = 2
        except Exception:
            logger.exception("[%s] - Error in on_enter_running_pumping", self.__class__.__name__)
        finally:
            self.bus_release()

    def on_exit_running_pumping(self):
        """ Stop the pump system
        """
        logger.info("[%s] - on_exit_running_pumping", self.__class__.__name__)
        self.bus_acquire()
        try:
            if self.thread_start_motor is not None:
                self.thread_start_motor.cancel()
                self.thread_start_motor = None
            self.stop_pump()
            self.thread_start_motor = threading.Timer(5, self.stop_inverter)
            self.thread_start_motor.start()
        except Exception:
            logger.exception("[%s] - Error in on_exit_running_pumping", self.__class__.__name__)
        finally:
            self.bus_release()

    def on_enter_running_waiting(self):
        """ Start the pump system
        """
        logger.info("[%s] - on_enter_running_waiting", self.__class__.__name__)
        self.bus_acquire()
        try:
            self.nodeman.find_value('led', 'blink').data = 'info'
            self.get_bus_value('state').data = 1
        except Exception:
            logger.exception("[%s] - Error in on_enter_running_waiting", self.__class__.__name__)
        finally:
            self.bus_release()

    def stop_check(self):
        """Check that the component is 'available'

        """
        if self.check_timer is not None:
            self.check_timer.cancel()
            self.check_timer = None

    def check_tempetatures(self):
        """Make a check using a timer.

        """
        #Check the temperatures
        freeze_temp = self.get_bus_value('temperature_freeze').data
        min_temp = self.get_bus_value('temperature_min').data
        temp1 = self.nodeman.find_value('temperature', 'temperature').data
        temp2 = self.nodeman.find_value('ambianceout', 'temperature').data
        if temp1 is None:
            temp1 = temp2
        if temp2 is None:
            logger.error("[%s] - Error in on_check : can't find temeprature sensors", self.__class__.__name__)
        else:
            temp = ( temp1 + temp2 ) / 2
            if temp < freeze_temp:
                self.freeze()
            if temp > min_temp and self.state == 'freezing':
                self.sleep()

    def check_levels(self):
        """Make a check using a timer.

        """
        if self.nodeman.find_value('level1', 'state') is not None:
            level1 = self.nodeman.find_value('level1', 'state').data
            level2 = self.nodeman.find_value('level2', 'state').data
            if level1==0 and level2==1:
                logger.error("[%s] - Error in on_check : incompatibles values in water levels", self.__class__.__name__)
            else:
                if level1 == 0:
                    self.wait()
                elif level2 == 1:
                    self.pump()
        else:
            self.pump()

    def check_battery(self):
        """Make a check using a timer.

        """
        #Check the temperatures
        battery_critical = self.get_bus_value('battery_critical').data
        battery_min = self.get_bus_value('battery_min').data
        battery = self.nodeman.find_value('battery', 'voltage').data
        solar = self.nodeman.find_value('solar', 'voltage').data
        if battery < battery_critical and self.state != 'sleeping':
            self.sleep()
        elif battery > battery_min and self.state == 'sleeping':
            self.charge()

    def on_check(self):
        """Make a check using a timer.

        """
        fire_again = True
        try:
            self.stop_check()
            self.check_battery()
            if self.state != 'sleeping':
                self.check_tempetatures()
                if self.state == 'charging':
                    self.check_levels()
            else:
                fire_again = False

        except Exception:
            logger.exception("[%s] - Error in on_check", self.__class__.__name__)
        if fire_again and self.check_timer is None and self.is_started:
            self.check_timer = threading.Timer(self.get_bus_value('timer_delay').data, self.on_check)
            self.check_timer.start()
            
    def start_pump(self):
        """Start the pump
        """
        pass
        
    def stop_pump(self):
        """Stop the pump
        """
        self.thread_start_motor = None
        pass
        
    def start_inverter(self):
        """Start the inverter
        """
        pass
        
    def stop_inverter(self):
        """Stop the pump
        """
        self.thread_start_motor = None
        pass
        
    def start(self, mqttc, trigger_thread_reload_cb=None):
        """Start the bus
        """
        for bus in self.buses:
            self.buses[bus].start(mqttc, trigger_thread_reload_cb=None)
        JNTFsmBus.start(self, mqttc, trigger_thread_reload_cb)

    def stop(self):
        """Stop the bus
        """
        self.stop_check()
        for bus in self.buses:
            self.buses[bus].stop()
        JNTFsmBus.stop(self)

    def loop(self, stopevent):
        """Retrieve data
        Don't do long task in loop. Use a separated thread to not perturbate the nodeman

        """
        for bus in self.buses:
            self.buses[bus].loop(stopevent)

class AmbianceComponent(DHTComponent):
    """ A component for ambiance """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', '%s.ambiance'%OID)
        name = kwargs.pop('name', "Ambiance sensor")
        DHTComponent.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

class CpuComponent(HardwareCpu):
    """ A water temperature component """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', '%s.cpu'%OID)
        name = kwargs.pop('name', "CPU")
        HardwareCpu.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

class ClockComponent(DS1307Component):
    """ A clock component """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', '%s.clock'%OID)
        name = kwargs.pop('name', "clock")
        DS1307Component.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

class AdsComponent(Ads1x15Component):
    """ An analogic to numeric converter component """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', '%s.ads'%OID)
        name = kwargs.pop('name', "ADS")
        Ads1x15Component.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

        uuid="voltage"
        self.values[uuid] = self.value_factory['sensor_integer'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The voltage',
            label='voltage',
            get_data_cb=self.read_data,
        )
        poll_value = self.values[uuid].create_poll_value(default=300)
        self.values[poll_value.uuid] = poll_value

        uuid="multiplier"
        self.values[uuid] = self.value_factory['config_float'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The voltage multiplier for A/D',
            label='mplr',
            default=1,
        )

    def read_voltage(self, node_uuid, index):
        try:
            ret = self.values['data'].data * self.values['multiplier'].data
        except Exception:
            logger.exception('[%s] - Exception when retrieving voltage', self.__class__.__name__)
            ret = None
        return ret
 
class TemperatureComponent(DS18B20):
    """ A water temperature component """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', '%s.temperature'%OID)
        name = kwargs.pop('name', "Temperature")
        DS18B20.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

class OutputComponent(GpioOut):
    """ An output component """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', '%s.output'%OID)
        name = kwargs.pop('name', "Output")
        GpioOut.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

class InputComponent(GpioIn):
    """ An input component """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', '%s.input'%OID)
        name = kwargs.pop('name', "Input")
        GpioIn.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

class LedComponent(GpioOut):
    """ A LED/Bulb to report status of the system"""

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', '%s.led'%OID)
        name = kwargs.pop('name', "Led")
        GpioOut.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        uuid="blink"
        self.values[uuid] = self.value_factory['blink'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The led to report state of the system.',
            label='LED',
            default='off',
            blink_off_cb=self.blink_off,
            blink_on_cb=self.blink_off,
        )
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

    def blink_on(self, node_uuid=None, index=0):
        """
        """
        self.set_state(node_uuid, index, 1)

    def blink_off(self, node_uuid=None, index=0):
        """
        """
        self.set_state(node_uuid, index, 0)

class HttpResourceComponent(BasicResourceComponent):
    """ A resource ie /rrd """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        product_name = kwargs.pop('product_name', "HTTP solarpump resource")
        name = kwargs.pop('name', "Http solarpump resource")
        BasicResourceComponent.__init__(self, path='solarpump', oid='http.solarpump', 
            bus=bus, addr=addr, name=name,
            product_name=product_name, **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

    def get_package_name(self):
        """Return the name of the package. Needed to publish static files

        **MUST** be copy paste in every extension that publish statics files
        """
        return __package__

    def check_heartbeat(self):
        """Check that the component is 'available'
        """
        return self.check_heartbeat_file('solarpump')
