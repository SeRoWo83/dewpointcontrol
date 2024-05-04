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

import logging
from time import struct_time
from configparser import RawConfigParser
from datetime import datetime
from threading import Event

import sht75
from uptime import uptime
from component import ComponentWithThread

from misc import CSV, delay

logger = logging.getLogger('fancontrol')

config: RawConfigParser = RawConfigParser()
config.read('fancontrol.cfg')
clock1 = config.getint('pins', 'sensor1_clock')
data1 = config.getint('pins', 'sensor1_data')
clock2 = config.getint('pins', 'sensor2_clock')
data2 = config.getint('pins', 'sensor2_data')

measure_interval = config.getint('measure', 'interval')
assert measure_interval >= 1


class Sensor(ComponentWithThread):
    def __init__(self) -> None:
        ut = uptime()
        super().__init__('sensor')
        self.S1 = sht75.Sensor(clock1, data1)
        self.S2 = sht75.Sensor(clock2, data2)
        self.event = Event()
        self.last_measurement = ut
        self.uptime = ut

    def __enter__(self) -> object:
        self.message_board.subscribe('Time', self, Sensor.on_time)
        return super().__enter__()

    def on_time(self, message: tuple[float, struct_time]) -> None:
        self.uptime, _ = message
        if self.uptime > self.last_measurement + 10.5:
            logger.warning(f'Interval between measurements > 10.5s: {self.last_measurement}, {self.uptime}.')
        if int(self.uptime) % measure_interval == 0 or self.uptime > self.last_measurement + 10.5:
            self.last_measurement = self.uptime
            self.event.set()

    def run(self) -> None:
        while self.message_board.query('ExitThread') is None:
            if self.event.wait(1):
                self.event.clear()
                # Start measurement approx. 250 ms after the full second.
                # This lowers interference with the DCF77 receiver.
                microsecond = datetime.now().microsecond
                wait = ((1250000 - microsecond) % 1000000) / 1000000.0
                assert wait >= 0
                assert wait < 1
                delay(wait)
                s1_data = self.S1.read()
                s2_data = self.S2.read()
                self.message_board.post('Measurement', (self.uptime, s1_data, s2_data))
                logger.info(CSV('measurement',
                                s1_data.humidity, s1_data.temperature, s1_data.tau, s1_data.error,
                                s2_data.humidity, s2_data.temperature, s2_data.tau, s2_data.error))


if __name__ == '__main__':
    with Sensor() as my_sensor:
        delay(2)
