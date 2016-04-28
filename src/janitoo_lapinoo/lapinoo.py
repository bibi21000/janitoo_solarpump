# -*- coding: utf-8 -*-
"""The Raspberry lapinoo

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

from janitoo.thread import JNTBusThread, BaseThread
from janitoo.options import get_option_autostart
from janitoo.utils import HADD
from janitoo.node import JNTNode
from janitoo.value import JNTValue
from janitoo.component import JNTComponent
from janitoo.bus import JNTBus

from janitoo_raspberry_camera.camera import CameraBus
from janitoo_raspberry_camera.camera import CameraPhoto, CameraVideo, CameraStream
from janitoo_raspberry_dht.dht import DHTComponent
from janitoo_raspberry_spi.bus_spi import SPIBus
from janitoo_raspberry_spi_ili9341.ili9341 import ScreenComponent as IliScreenComponent
from janitoo_raspberry_spi_pn532.pn532 import PN532Component
from janitoo_raspberry_i2c.bus_i2c import I2CBus
from janitoo_raspberry_i2c_vcnl40xx.vcnl40xx import VCLN4010Component
from janitoo_raspberry_i2c_ds1307.ds1307 import DS1307Component
from janitoo_raspberry_gpio.gpio import GpioBus, OutputComponent, RGBComponent

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

def make_ambiance(**kwargs):
    return AmbianceComponent(**kwargs)

def make_screen(**kwargs):
    return ScreenComponent(**kwargs)

def make_led(**kwargs):
    return LedComponent(**kwargs)

def make_proximity(**kwargs):
    return ProximityComponent(**kwargs)

def make_rfid(**kwargs):
    return RfidComponent(**kwargs)

def make_rtc(**kwargs):
    return RtcComponent(**kwargs)

def make_photo(**kwargs):
    return PhotoComponent(**kwargs)

def make_video(**kwargs):
    return VideoComponent(**kwargs)

def make_videostream(**kwargs):
    return VideoStreamComponent(**kwargs)

def make_audiostream(**kwargs):
    return AudioStreamComponent(**kwargs)

class LapinooBus(JNTBus):
    """A bus to manage Lapinoo
    """
    def __init__(self, **kwargs):
        """
        """
        JNTBus.__init__(self, **kwargs)
        self.buses = {}
        self.buses['camera'] = CameraBus(masters=[self], **kwargs)
        self.buses['gpiobus'] = GpioBus(masters=[self], **kwargs)
        self.buses['spibus'] = SPIBus(masters=[self], **kwargs)
        self.buses['i2cbus'] = I2CBus(masters=[self], **kwargs)
        self._lapinoo_lock =  threading.Lock()
        self.check_timer = None
        uuid="timer_delay"
        self.values[uuid] = self.value_factory['config_integer'](options=self.options, uuid=uuid,
            node_uuid=self.uuid,
            help='The delay between 2 checks',
            label='Timer.',
            default=45,
        )

    def stop_check(self):
        """Check that the component is 'available'

        """
        if self.check_timer is not None:
            self.check_timer.cancel()
            self.check_timer = None

    def on_check(self):
        """Make a check using a timer.

        """
        self.stop_check()
        if self.check_timer is None and self.is_started:
            self.check_timer = threading.Timer(self.values['timer_delay'].data, self.on_check)
            self.check_timer.start()
        state = True
        #~ if self.nodeman.is_started:
            #~ #Check the state of some "importants sensors
            #~ try:
                #~ temp1 = self.nodeman.find_value('surftemp', 'temperature')
                #~ if temp1 is None or temp1.data is None:
                    #~ logger.warning('temp1 problemm')
                #~ temp2 = self.nodeman.find_value('deeptemp', 'temperature')
                #~ if temp2 is None or temp2.data is None:
                    #~ logger.warning('temp2 problem')
            #~ except:
                #~ logger.exception("[%s] - Error in on_check", self.__class__.__name__)
        #~ if self.nodeman.is_started:
            #~ #Update the cycles
            #~ try:
                #~ moon = self.nodeman.find_value('moon', 'factor_now')
                #~ moonled = self.nodeman.find_value('ledmoon', 'level')
                #~ max_moonled = self.nodeman.find_value('ledmoon', 'max_level')
                #~ moonled.data = int(max_moonled.data * moon.data)
                #~ sun = self.nodeman.find_value('sun', 'factor_now')
                #~ sunled = self.nodeman.find_value('ledsun', 'level')
                #~ max_sunled = self.nodeman.find_value('ledsun', 'max_level')
                #~ sunled.data = int(max_sunled.data * sun.data)
            #~ except:
                #~ logger.exception("[%s] - Error in on_check", self.__class__.__name__)
        #~ if self.nodeman.is_started:
            #~ #Update the fullsun
            #~ try:
                #~ switch = self.nodeman.find_value('switch_fullsun', 'switch')
                #~ sun = self.nodeman.find_value('sun', 'factor_now')
                #~ if sun.data > 0.8:
                    #~ #Set fullsun on
                    #~ switch.data = 'on'
                #~ elif sun.data < 0.79:
                    #~ #Set fullsun off
                    #~ switch.data = 'on'
            #~ except:
                #~ logger.exception("[%s] - Error in on_check", self.__class__.__name__)

    def start(self, mqttc, trigger_thread_reload_cb=None):
        """Start the bus
        """
        for bus in self.buses:
            self.buses[bus].start(mqttc, trigger_thread_reload_cb=None)
        JNTBus.start(self, mqttc, trigger_thread_reload_cb)
        self.on_check()

    def stop(self):
        """Stop the bus
        """
        self.stop_check()
        JNTBus.stop(self)
        for bus in self.buses:
            self.buses[bus].stop()
        #~ Not needed as the components will be stopped by the slave buses

    def check_heartbeat(self):
        """Check that the component is 'available'

        """
        res = True
        #~ for bus in self.buses:
            #~ res = res and self.buses[bus].check_heartbeat()
        return res

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
        oid = kwargs.pop('oid', 'lapinoo.ambiance')
        name = kwargs.pop('name', "Ambiance sensor")
        DHTComponent.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

class ProximityComponent(VCLN4010Component):
    """ A component for a DC motor """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', 'lapinoo.dcmotor')
        name = kwargs.pop('name', "Proximity sensor")
        VCLN4010Component.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

class RtcComponent(VCLN4010Component):
    """ A component for RTC """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', 'lapinoo.rtc')
        name = kwargs.pop('name', "RTC clock")
        DS1307Component.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

class LedComponent(RGBComponent):
    """ A component for a RGB Led (PWM) """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', 'lapinoo.led')
        name = kwargs.pop('name', "Heart Led")
        RGBComponent.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

class ScreenComponent(IliScreenComponent):
    """ A timelapse component """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', 'lapinoo.screen')
        name = kwargs.pop('name', "Screen")
        IliScreenComponent.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

class PhotoComponent(CameraPhoto):
    """ A timelapse component """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', 'lapinoo.photo')
        name = kwargs.pop('name', "Photo")
        CameraPhoto.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

class VideoComponent(CameraVideo):
    """ A timelapse component """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', 'lapinoo.video')
        name = kwargs.pop('name', "Video recorder")
        CameraVideo.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

class VideoStreamComponent(CameraStream):
    """ A video stream component """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', 'lapinoo.videostream')
        name = kwargs.pop('name', "Video stream")
        CameraStream.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

class AudioStreamComponent(CameraStream):
    """ An audio stream component """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', 'lapinoo.audiostream')
        name = kwargs.pop('name', "Audio stream")
        CameraStream.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)

class RfidComponent(PN532Component):
    """ An RFID component """

    def __init__(self, bus=None, addr=None, **kwargs):
        """
        """
        oid = kwargs.pop('oid', 'lapinoo.rfid')
        name = kwargs.pop('name', "RFID reader/writer")
        PN532Component.__init__(self, oid=oid, bus=bus, addr=addr, name=name,
                **kwargs)
        logger.debug("[%s] - __init__ node uuid:%s", self.__class__.__name__, self.uuid)
