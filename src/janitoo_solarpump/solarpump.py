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
import os
import threading

from janitoo.thread import JNTBusThread

from janitoo_factory.buses.fsm import JNTFsmBus
from janitoo_factory.threads.http import BasicResourceComponent

from janitoo_raspberry_dht.dht import DHTComponent
from janitoo_raspberry_gpio.gpio import GpioBus, OutputComponent as GpioOut, InputComponent as GpioIn
from janitoo_raspberry_i2c.bus_i2c import I2CBus
from janitoo_raspberry_i2c_ds1307.ds1307 import DS1307Component
from janitoo_raspberry_i2c_ads1x15.ads import ADSComponent as Ads1x15Component
from janitoo_raspberry_i2c_ina219.ina import INA219Component as I2CINA219Component
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

def make_ina219(**kwargs):
    return INA219Component(**kwargs)

def make_http_resource(**kwargs):
    return HttpResourceComponent(**kwargs)

#~ def make_pump(**kwargs):
    #~ return PumpComponent(**kwargs)

#~ def make_pir(**kwargs):
    #~ return PirComponent(**kwargs)

#~ def make_proximity(**kwargs):
    #~ return ProximityComponent(**kwargs)

class OffGridBus(JNTFsmBus):
    """A bus to manage Solar/Wind powered systems. It use a state machine to manage : boot, charge, sleep and running states.
    """

    def __init__(self, **kwargs):
        """
        """
        JNTFsmBus.__init__(self, **kwargs)
        self.states = [
           'booting',
           'halted',
           'sleeping',
           'charging',
           'running',
        ]
        """The solarpump states :
            - booting : the system starts. 
            - halted : the system is halted. 
            - sleeping : the power is very low, we do not poll sensors again (except the battery ones). 
            - charging : power is low. We can poll sensors again.
            - running : power is ok. We may run
        """

        self.transitions = [
            { 'trigger': 'boot',
                'source': ['booting','halted'],
                'dest': 'sleeping',
                'conditions': 'condition_booting',
                'after': 'publish_state',
            },
            { 'trigger': 'halt',
                'source': '*',
                'dest': 'halted',
            },
            { 'trigger': 'sleep',
                'source': '*',
                'dest': 'sleeping',
                'conditions': 'condition_sleeping',
                'after': 'publish_state',
            },
            { 'trigger': 'charge',
                'source': ['sleeping', 'running'],
                'dest': 'charging',
                'conditions': 'condition_charging',
                'after': 'publish_state',
            },
            { 'trigger': 'run',
                'source': 'charging',
                'dest': 'running',
                'conditions': 'condition_running',
                'after': 'publish_state',
            },
        ]
        self.buses = {}
        self.buses['gpiobus'] = GpioBus(masters=[self], **kwargs)
        self.buses['1wire'] = OnewireBus(masters=[self], **kwargs)
        self.buses['i2c'] = I2CBus(masters=[self], **kwargs)
        
        self.check_timer = None
 
        timer_delay = kwargs.get('timer_delay', 10)
        uuid="{:s}_timer_delay".format(OID)
        self.values[uuid] = self.value_factory['config_integer'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The delay between 2 checks',
            label='Timer.',
            default=timer_delay,
        )

        uuid="{:s}_battery_critical".format(OID)
        self.values[uuid] = self.value_factory['config_float'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The critical level for battery.',
            label='Batt crit',
            default=11.6,
            unit='V',
        )

        uuid="{:s}_battery_min".format(OID)
        self.values[uuid] = self.value_factory['config_float'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The minimal level for battery.',
            label='Batt min',
            default=12.5,
            unit='V',
        )

        uuid="{:s}_battery_diff".format(OID)
        self.values[uuid] = self.value_factory['config_float'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The minimal difference for battery voltage to change state.',
            label='Batt diff',
            default=0.2,
            unit='V',
        )

        self.thread_fan = None

    @property
    def booting_sensors(self):
        """The sensors we will poll at boot
        """
        opt_sensors = set()
        if self.nodeman.find_node('led_error') is not None:
            opt_sensors.add(self.nodeman.find_value('led_error', 'state'))
        if self.nodeman.find_node('led') is not None:
            opt_sensors.add(self.nodeman.find_value('led', 'state'))
        if self.nodeman.find_node('solar') is not None:
            opt_sensors.add(self.nodeman.find_value('solar', 'voltage'))
        opt_sensors.add(self.nodeman.find_value('battery', 'voltage'))
        return opt_sensors

    @property
    def sleeping_sensors(self):
        """The sensors we will poll when sleeping
        """
        opt_sensors = set()
        if self.nodeman.find_node('ina219') is not None:
            opt_sensors.add(self.nodeman.find_value('ina219', 'power'))
        return opt_sensors.union( self.booting_sensors )

    @property
    def charging_sensors(self):
        """The sensors we will poll when charging
        """
        opt_sensors = set()
        if self.nodeman.find_node('fan') is not None:
            opt_sensors.add(self.nodeman.find_value('fan', 'state'))
        if self.nodeman.find_node('fan_battery') is not None:
            opt_sensors.add(self.nodeman.find_value('fan_battery', 'state'))
        if self.nodeman.find_node('temp_battery') is not None:
            opt_sensors.add(self.nodeman.find_value('temp_battery', 'temperature'))
        if self.nodeman.find_node('ambiancein') is not None:
            opt_sensors.add(self.nodeman.find_value('ambiancein', 'temperature'))
        opt_sensors.add(self.nodeman.find_value('cpu', 'temperature'))
        opt_sensors.add(self.nodeman.find_value('cpu', 'voltage'))
        return opt_sensors.union( self.sleeping_sensors )

    @property
    def running_sensors(self):
        """The sensors we will poll when running
        """
        opt_sensors = set()
        if self.nodeman.find_node('ambiancein') is not None:
            opt_sensors.add(self.nodeman.find_value('ambiancein', 'humidity'))
        opt_sensors.add(self.nodeman.find_value('cpu', 'frequency'))
        return opt_sensors.union( self.charging_sensors )

    def condition_booting(self):
        """Return True if all sensors are available
        """
        polled_sensors = self.booting_sensors
        logger.debug("[%s] - condition_booting sensors : %s", self.__class__.__name__, polled_sensors)
        return all(v is not None for v in polled_sensors)

    def condition_sleeping(self):
        """Return True if all sensors are available
        """
        polled_sensors = self.sleeping_sensors
        logger.debug("[%s] - condition_sleeping sensors : %s", self.__class__.__name__, polled_sensors)
        return all(v is not None for v in polled_sensors)

    def condition_charging(self):
        """Return True if all sensors are available
        """
        polled_sensors = self.charging_sensors
        logger.debug("[%s] - condition_charging sensors : %s", self.__class__.__name__, polled_sensors)
        return all(v is not None for v in polled_sensors)

    def condition_running(self):
        """Return True if all sensors are available
        """
        polled_sensors = self.running_sensors
        logger.debug("[%s] - condition_running sensors : %s", self.__class__.__name__, polled_sensors)
        return all(v is not None for v in polled_sensors)

    def on_enter_sleeping(self):
        """
        """
        logger.debug("[%s] - on_enter_sleeping", self.__class__.__name__)
        self.fsm_bus_acquire()
        try:
            self.nodeman.remove_polls(self.running_sensors - self.sleeping_sensors)
            self.nodeman.add_polls(self.sleeping_sensors, slow_start=True, overwrite=False)
            self.nodeman.find_value('led', 'blink').data = 'off'
        except Exception:
            logger.exception("[%s] - Error in on_enter_sleeping", self.__class__.__name__)
        finally:
            self.fsm_bus_release()
        self.start_check()
        try:
            self.publish_state()
        except Exception:
            logger.exception("[%s] - Error when publishing state", self.__class__.__name__)

    def on_enter_halted(self):
        """
        """
        logger.info("[%s] - on_enter_halted", self.__class__.__name__)
        self.stop_check()
        self.fsm_bus_acquire()
        try:
            self.nodeman.remove_polls(self.running_sensors)
            self.nodeman.find_value('led', 'blink').data = 'off'
        except Exception:
            logger.exception("[%s] - Error in on_enter_halted", self.__class__.__name__)
        finally:
            self.fsm_bus_release()
        JNTFsmBus.on_enter_halted(self)

    def on_enter_booting(self):
        """
        """
        logger.info("[%s] - on_enter_booting", self.__class__.__name__)
        self.stop_check()
        self.fsm_bus_acquire()
        try:
            self.nodeman.remove_polls(self.running_sensors - self.sleeping_sensors)
            self.nodeman.add_polls(self.sleeping_sensors, slow_start=True, overwrite=False)
            self.nodeman.find_value('led', 'blink').data = 'alert'
        except Exception:
            logger.exception("[%s] - Error in on_enter_booting", self.__class__.__name__)
        finally:
            self.fsm_bus_release()
        try:
            self.publish_state()
        except Exception:
            logger.exception("[%s] - Error when publishing state", self.__class__.__name__)

    def on_enter_charging(self):
        """
        """
        logger.info("[%s] - on_enter_charging", self.__class__.__name__)
        self.fsm_bus_acquire()
        try:
            self.nodeman.remove_polls(self.running_sensors - self.charging_sensors)
            self.nodeman.add_polls(self.charging_sensors, slow_start=True, overwrite=False)
            self.nodeman.find_value('led', 'blink').data = 'alert'
        except Exception:
            logger.exception("[%s] - Error in on_enter_charging", self.__class__.__name__)
        finally:
            self.fsm_bus_release()
        try:
            self.publish_state()
        except Exception:
            logger.exception("[%s] - Error when publishing state", self.__class__.__name__)

    def on_enter_running(self):
        """
        """
        logger.info("[%s] - on_enter_running", self.__class__.__name__)
        self.fsm_bus_acquire()
        try:
            self.nodeman.find_value('led', 'blink').data = 'heartbeat'
            self.nodeman.add_polls(self.running_sensors, slow_start=True, overwrite=False)
        except Exception:
            logger.exception("[%s] - Error in on_enter_running", self.__class__.__name__)
        finally:
            self.fsm_bus_release()
        try:
            self.publish_state()
        except Exception:
            logger.exception("[%s] - Error when publishing state", self.__class__.__name__)

    def on_exit_running(self):
        """
        """
        logger.info("[%s] - on_enter_running", self.__class__.__name__)
        self.fsm_bus_acquire()
        try:
            self.nodeman.find_value('led', 'blink').data = 'off'
            self.nodeman.remove_polls(self.running_sensors-self.running_sensors - self.sleeping_sensors)
        except Exception:
            logger.exception("[%s] - Error in on_enter_running", self.__class__.__name__)
        finally:
            self.fsm_bus_release()
        try:
            self.publish_state()
        except Exception:
            logger.exception("[%s] - Error when publishing state", self.__class__.__name__)

    def stop_check(self):
        """Check that the component is 'available'

        """
        if self.check_timer is not None:
            self.check_timer.cancel()
            self.check_timer = None

    def start_check(self):
        """Check that the component is 'available'

        """
        if self.check_timer is None and self.is_started and self.get_bus_value('timer_delay').data != 0:
            self.check_timer = threading.Timer(self.get_bus_value('timer_delay').data, self.on_check)
            self.check_timer.start()

    def on_check(self, **kwargs):
        """Make a check using a timer.

        """
        pass
        
    def start(self, mqttc, trigger_thread_reload_cb=None, **kwargs):
        """Start the bus
        """
        for bus in self.buses:
            self.buses[bus].start(mqttc, trigger_thread_reload_cb=None, **kwargs)
        JNTFsmBus.start(self, mqttc, trigger_thread_reload_cb, **kwargs)

    def stop(self, **kwargs):
        """Stop the bus
        """
        if hasattr(self, "halt"):
            self.halt()
        if self.thread_start_motor is not None:
            self.thread_start_motor.join()
            self.thread_start_motor = None
         
        self.stop_buses(self.buses, **kwargs)
        JNTFsmBus.stop(self, **kwargs)

    def loop(self, stopevent):
        """Retrieve data
        Don't do long task in loop. Use a separated thread to not perturbate the nodeman

        """
        for bus in self.buses:
            self.buses[bus].loop(stopevent)


class SolarpumpBus(OffGridBus):
    """A bus to manage Solarpump
    """

    """The solarpump states :
        - sleeping : the power is very low, we do not poll sensors again (except the battery ones, 
        - charging : power is low. We can poll sensors again.
        - running : power is ok. We may pump
            - pumping : the pump is on !!!
            - freezing : stop pumping !!!
            - waiting : waiting for water
    """


    def __init__(self, **kwargs):
        """
        """
        OffGridBus.__init__(self, **kwargs)

        self.transitions.extend( [
            { 'trigger': 'freeze',
                'source': '*',
                'dest': 'running_freezing',
                'conditions': 'condition_sleeping',
                'after': 'publish_state',
            },
            { 'trigger': 'pump',
                'source': ['running','charging'],
                'dest': 'running_pumping',
                'conditions': 'condition_running',
                'after': 'publish_state',
            },
            { 'trigger': 'wait',
                'source': ['running','charging'],
                'dest': 'running_waiting',
                'conditions': 'condition_running',
                'after': 'publish_state',
            },
        ] )
        
        self.states.remove('running')
        self.states.append( { 'name': 'running',
            'children': ['freezing','pumping', 'waiting'],
        } )
               
        uuid="{:s}_temperature_freeze".format(OID)
        self.values[uuid] = self.value_factory['config_float'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The feezing temperature.',
            label='Temp Freeze',
            default=-1,
        )

        uuid="{:s}_temperature_min".format(OID)
        self.values[uuid] = self.value_factory['config_float'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The minimum temperature to restart pumping.',
            label='Temp Min',
            default=4,
        )

        pump_delay = kwargs.get('pump_delay', 10)
        uuid="{:s}_pump_delay".format(OID)
        self.values[uuid] = self.value_factory['config_integer'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The delay between inverter and pump',
            label='Delay',
            default=pump_delay,
        )
        
        self.thread_start_motor = None

    def stop(self, **kwargs):
        """Stop the bus
        """
        if self.thread_start_motor is not None:
            self.thread_start_motor.join()
            self.thread_start_motor = None
        OffGridBus.stop(self, **kwargs)

    @property
    def sleeping_sensors(self):
        """The sensors we will poll
        """
        opt_sensors = set()
        opt_sensors.add(self.nodeman.find_value('temperature', 'temperature'))
        opt_sensors.add(self.nodeman.find_value('ambianceout', 'temperature'))
        return opt_sensors.union( super(SolarpumpBus, self).sleeping_sensors )

    @property
    def running_sensors(self):
        """The sensors we will poll
        """
        opt_sensors = set()
        if self.nodeman.find_node('level1') is not None:
            opt_sensors.add(self.nodeman.find_value('level1', 'state'))
            opt_sensors.add(self.nodeman.find_value('level2', 'state'))
        opt_sensors.add(self.nodeman.find_value('ambianceout', 'humidity'))
        opt_sensors.add(self.nodeman.find_value('pump', 'state'))
        opt_sensors.add(self.nodeman.find_value('inverter', 'state'))
        return opt_sensors.union( super(SolarpumpBus, self).running_sensors)

    def on_enter_running_freezing(self):
        """
        """
        logger.info("[%s] - on_enter_running_freezing", self.__class__.__name__)
        self.fsm_bus_acquire()
        try:
            self.nodeman.find_value('led', 'blink').data = 'notify'
        except Exception:
            logger.exception("[%s] - Error in on_enter_running_freezing", self.__class__.__name__)
        finally:
            self.fsm_bus_release()

    def on_enter_running_pumping(self):
        """ Start the pump system
        """
        logger.info("[%s] - on_enter_running_pumping", self.__class__.__name__)

        self.fsm_bus_acquire()
        try:
            if self.thread_start_motor is not None:
                self.thread_start_motor.cancel()
                self.thread_start_motor = None
            self.nodeman.find_value('led', 'blink').data = 'info1'
            self.start_inverter()
            self.thread_start_motor = threading.Timer(self.get_bus_value('pump_delay').data, self.start_pump)
            self.thread_start_motor.start()
        except Exception:
            logger.exception("[%s] - Error in on_enter_running_pumping", self.__class__.__name__)
        finally:
            self.fsm_bus_release()
        try:
            self.publish_state()
        except Exception:
            logger.exception("[%s] - Error when publishing state", self.__class__.__name__)

    def on_exit_running_pumping(self):
        """ Stop the pump system
        """
        logger.info("[%s] - on_exit_running_pumping", self.__class__.__name__)
        self.fsm_bus_acquire()
        try:
            if self.thread_start_motor is not None:
                self.thread_start_motor.cancel()
                self.thread_start_motor = None
            self.stop_pump()
            self.thread_start_motor = threading.Timer(self.get_bus_value('pump_delay').data, self.stop_inverter)
            self.thread_start_motor.start()
        except Exception:
            logger.exception("[%s] - Error in on_exit_running_pumping", self.__class__.__name__)
        finally:
            self.fsm_bus_release()

    def on_enter_running_waiting(self):
        """ Start the pump system
        """
        logger.info("[%s] - on_enter_running_waiting", self.__class__.__name__)
        self.fsm_bus_acquire()
        try:
            self.nodeman.find_value('led', 'blink').data = 'info'
        except Exception:
            logger.exception("[%s] - Error in on_enter_running_waiting", self.__class__.__name__)
        finally:
            self.fsm_bus_release()
        try:
            self.publish_state()
        except Exception:
            logger.exception("[%s] - Error when publishing state", self.__class__.__name__)


    def check_temperatures(self, **kwargs):
        """Make a check using a timer.

        """
        #Check the temperatures
        fan_temp = kwargs.get('fan_temp', None)
        if fan_temp is None:
            fan_temp = self.get_bus_value('temperature_fan').data
        min_temp = kwargs.get('min_temp', None)
        freeze_temp = kwargs.get('freeze_temp', None)
        if freeze_temp is None:
            freeze_temp = self.get_bus_value('temperature_freeze').data
        min_temp = kwargs.get('min_temp', None)
        if min_temp is None:
            min_temp = self.get_bus_value('temperature_min').data
        temp1 = kwargs.get('temp1', None)
        if temp1 is None:
            temp1 = self.nodeman.find_value('temperature', 'temperature').data
        temp2 = kwargs.get('temp2', None)
        if temp2 is None:
            temp2 = self.nodeman.find_value('ambianceout', 'temperature').data
        temp_battery = kwargs.get('temp_battery', None)
        if temp_battery is None:
            temp_battery = self.nodeman.find_value('temp_battery', 'temperature').data

        if temp1 is None:
            temp1 = temp2
        if temp2 is None:
            logger.error("[%s] - Error in on_check : can't find temeprature sensors", self.__class__.__name__)
        else:
            temp = ( temp1 + temp2 ) / 2
            if temp < freeze_temp and self.state != 'sleeping':
                self.freeze()
            if temp > min_temp and self.state == 'running_freezing':
                self.wait()

    def check_levels(self, **kwargs):
        """Make a check using a timer.

        """
        level1 = kwargs.get('level1', None)
        if level1 is None:
            level1 = self.nodeman.find_value('level1', 'state').data
        if level1 is not None:
            level2 = kwargs.get('level2', None)
            if level2 is None:
                level2 = self.nodeman.find_value('level2', 'state').data
            if level1==0 and level2==1:
                self.wait()
                logger.error("[%s] - Error in on_check : incompatibles values in water levels", self.__class__.__name__)
            else:
                if level1 == 0:
                    self.wait()
                elif level2 == 1:
                    self.pump()
        else:
            self.pump()

    def check_battery(self, **kwargs):
        """Make a check using a timer.

        """
        #Check the temperatures
        battery_critical = kwargs.get('battery_critical', None)
        if battery_critical is None:
            battery_critical = self.get_bus_value('battery_critical').data
        battery_min = kwargs.get('battery_min', None)
        if battery_min is None:
            battery_min = self.get_bus_value('battery_min').data
        battery = kwargs.get('battery', None)
        if battery is None:
            battery = self.nodeman.find_value('battery', 'voltage').data
            
        if battery < battery_critical:
            self.sleep()
        elif battery < battery_min:
            self.charge()
        elif battery > battery_min + 0.2:
            if self.state == 'sleeping':
                self.charge()
            elif self.state == 'charging':
                self.run()

    def on_check(self, **kwargs):
        """Make a check using a timer.

        """
        fire_again = True
        delay_mult = 1
        
        try:
            self.stop_check()
            self.check_battery(**kwargs)
            if self.state != 'sleeping':
                self.check_temperatures(**kwargs)
                if self.state in ['running', 'running_pumping', 'running_waiting']:
                    self.check_levels(**kwargs)
            else:
                fire_again = False
            if self.state == 'sleeping':
                delay_mult = 3
        except Exception:
            logger.exception("[%s] - Error in on_check", self.__class__.__name__)

        fire_again = kwargs.get('fire_again', fire_again)
        timer_delay = kwargs.get('timer_delay', self.get_bus_value('timer_delay').data)
        if fire_again:
            self.start_check()
            
    def start_pump(self):
        """Start the pump
        """
        pass
        
    def stop_pump(self):
        """Stop the pump
        """
        self.thread_start_motor = None
        
    def start_inverter(self):
        """Start the inverter
        """
        pass
        
    def stop_inverter(self):
        """Stop the pump
        """
        self.thread_start_motor = None

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

class INA219Component(I2CINA219Component):
    """ A component """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', '%s.ina219'%OID)
        name = kwargs.pop('name', "INA219")
        I2CINA219Component.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
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
