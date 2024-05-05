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

from numpy import NaN

from component import Component
from sht75 import SensorData
from uptime import uptime as global_uptime

logger = logging.getLogger('fancontrol')


class Average(Component):
    def __init__(self) -> None:
        super().__init__('average')
        self.deque = deque(maxlen=9000)  # enough for 24h

    def __enter__(self) -> object:
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

            T1 = 0
            rH1 = 0
            tau1 = 0
            count1 = 0
            T2 = 0
            rH2 = 0
            tau2 = 0
            count2 = 0

            for uptime, s1_data, s2_data in self.deque:
                assert uptime <= uptime0
                if uptime0 - uptime > timespan:
                    break
                if not s1_data.error:
                    T1 += s1_data.temperature
                    rH1 += s1_data.humidity
                    tau1 += s1_data.tau
                    count1 += 1
                if not s2_data.error:
                    T2 += s2_data.temperature
                    rH2 += s2_data.humidity
                    tau2 += s2_data.tau
                    count2 += 1
            if count1 > 0:
                T1 /= count1
                rH1 /= count1
                tau1 /= count1
            error1 = count1 < max(1, timespan / 20)
            if count2 > 0:
                T2 /= count2
                rH2 /= count2
                tau2 /= count2
            error2 = count2 < max(1, timespan / 20)
            return (SensorData(humidity=rH1, temperature=T1, tau=tau1, error=error1),
                    SensorData(humidity=rH2, temperature=T2, tau=tau2, error=error2))
