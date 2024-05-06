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

from collections import deque
import logging
from typing import Self

from component import Component
from sht75 import SensorData
from uptime import uptime as global_uptime

logger = logging.getLogger('fancontrol')


class Average(Component):
    def __init__(self) -> None:
        super().__init__('average')
        self.deque = deque(maxlen=9000)  # enough for 24h

    def __enter__(self) -> Self:
        with self.lock:
            self.message_board.subscribe('Measurement', self, Average.on_measurement)
            self.message_board.subscribe('Average', self, Average.on_average)
        return super().__enter__()

    def on_measurement(self, message: int) -> None:
        with self.lock:
            self.deque.appendleft(message)

    def on_average(self, message: int) -> tuple[SensorData, SensorData]:
        with self.lock:
            uptime0 = global_uptime()
            timespan = message

            temperature1: float = 0.0
            temperature2: float = 0
            humidity1: float = 0.0
            humidity2: float = 0
            dewpoint1: float = 0.0
            dewpoint2: float = 0
            count1: int = 0
            count2: int = 0

            for uptime, s1_data, s2_data in self.deque:
                assert uptime <= uptime0
                if uptime0 - uptime > timespan:
                    break
                if not s1_data.error:
                    temperature1 += s1_data.temperature
                    humidity1 += s1_data.humidity
                    dewpoint1 += s1_data.dewpoint
                    count1 += 1
                if not s2_data.error:
                    temperature2 += s2_data.temperature
                    humidity2 += s2_data.humidity
                    dewpoint2 += s2_data.dewpoint
                    count2 += 1
            if count1 > 0:
                temperature1 /= count1
                humidity1 /= count1
                dewpoint1 /= count1
            error1 = count1 < max(1.0, timespan / 20)
            if count2 > 0:
                temperature2 /= count2
                humidity2 /= count2
                dewpoint2 /= count2
            error2 = count2 < max(1.0, timespan / 20)
            return (SensorData(humidity=humidity1, temperature=temperature1, dewpoint=dewpoint1, error=error1),
                    SensorData(humidity=humidity2, temperature=temperature2, dewpoint=dewpoint2, error=error2))
