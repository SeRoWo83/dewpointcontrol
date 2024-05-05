#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Copyright © 2016 Daniel Müllner <https://danifold.net>
    All changes from 2017-12-27 on: Copyright © Google Inc. <https://google.com>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

import RPi.GPIO as GPIO
from configparser import RawConfigParser

'''
Switch a LED on (and leave it on). This is useful as a status signal whether
the Raspberry Pi is still working or has finished the shutdown sequence.
At shutdown, all GPIO ports are reconfigured as input, and the LED goes out.
'''

config = RawConfigParser()
config.read('fancontrol.cfg')
led_pin = config.getint('pins', 'led')
GPIO.setmode(GPIO.BOARD)
GPIO.setup(led_pin, GPIO.OUT, initial=GPIO.HIGH)
