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

# Set default logging handler to avoid "No handler found" warnings.
import logging
logger = logging.getLogger(__name__)
import os

from janitoo.thread import JNTBusThread
from janitoo.options import get_option_autostart

##############################################################
#Check that we are in sync with the official command classes
#Must be implemented for non-regression
from janitoo.classes import COMMAND_DESC

COMMAND_CONTROLLER = 0x1050

assert(COMMAND_DESC[COMMAND_CONTROLLER] == 'COMMAND_CONTROLLER')
##############################################################

from janitoo_solarpump import OID

def make_thread(options, force=False):
    if get_option_autostart(options, OID) or force:
        return SolarpumpThread(options)
    else:
        return None

class SolarpumpThread(JNTBusThread):
    """The basic thread

    """
    def init_bus(self):
        """Build the bus
        """
        from janitoo_solarpump.solarpump import SolarpumpBus
        self.section = OID
        self.bus = SolarpumpBus(options=self.options, oid=self.section, product_name="Raspberry solarpump controller")

