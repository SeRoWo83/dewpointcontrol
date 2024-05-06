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
from math import expm1
from time import struct_time
from configparser import RawConfigParser
from typing import Self

from component import Component

DEBUG = False

logger = logging.getLogger('fancontrol')

config = RawConfigParser()
config.read('fancontrol.cfg')
ventilation_period = config.getfloat('fan', 'ventilation_period')


class Fan(Component):
    def __init__(self) -> None:
        super().__init__('fan')
        self.mode = None
        self.fanState = None
        self.lastOff = None
        self.stayOnUntil = 0
        self.stayOffUntil = 0

    def __enter__(self) -> Self:
        with self.lock:
            self.message_board.subscribe('Mode', self, Fan.on_mode)
            self.message_board.subscribe('Time', self, Fan.on_time)
        return super().__enter__()

    def on_mode(self, message) -> None:
        with self.lock:
            self.mode = message
            assert self.mode in ('auto', 'manual')
            if self.mode != 'manual':
                self.fanState = None
                self.lastOff = -90000
                self.stayOnUntil = 0
                self.stayOffUntil = 0

    def decide_fan(self, uptime: float) -> bool:
        if self.stayOffUntil > uptime:
            return False

        average1 = self.message_board.ask('Average', 60)
        average10 = self.message_board.ask('Average', 60 * 10)

        if average1 is None or average10 is None:
            logger.error('fan, Average is None.')
            self.message_board.post('FanComment', 'Error!')
            return False

        s1_data = average1[0]
        s2_data = average10[1]
        if s1_data.error or s2_data.error:
            self.message_board.post('FanComment', 'Not enough samples for average.')
            return False

        if s1_data.tau - s2_data.tau < 1:
            self.message_board.post('FanComment', 'High outside dew point.')
            self.stayOffUntil = uptime + 20 * 60
            return False

        if s1_data.temperature < s2_data.temperature:
            self.message_board.post('FanComment', 'Permanent ventilation: warm and dry outside.')
            self.stayOnUntil = uptime + 20 * 60
            return True

        if s1_data.temperature < 10:
            self.message_board.post('FanComment', 'Low room temperature.')
            self.stayOffUntil = uptime + 20 * 60
            return False

        remaining_ventilation_period = self.stayOnUntil - uptime
        if remaining_ventilation_period > 0:
            self.message_board.post('FanComment',
                                    f'Remaing ventilation period: {int(remaining_ventilation_period / 60.0 + .5)} min.')
            return True

        off_seconds = expm1((15.0 - s2_data.temperature) / 10.0) * 45 * 60

        if off_seconds < 60:
            off_seconds = 0
        if off_seconds > 86400:
            off_seconds = 86400
        if self.lastOff is None:
            remaining_wait_period = off_seconds
        else:
            remaining_wait_period = max(0, off_seconds - uptime + self.lastOff)
        self.message_board.post('FanComment', f'Wait period: {int(off_seconds / 60.0 + .5)} min '
                                              f'({int(remaining_wait_period / 60.0 + .5)} min remaining).')
        self.message_board.post('WaitPeriod', off_seconds)
        self.message_board.post('RemainingWaitPeriod', remaining_wait_period)
        fan_state = remaining_wait_period == 0
        if fan_state:
            self.stayOnUntil = uptime + 20 * 60
        return fan_state

    def on_time(self, message: tuple[float, struct_time]) -> None:
        with self.lock:
            if self.mode == 'manual':
                return
            uptime, _ = message
            action: bool = self.decide_fan(uptime)

            if action != self.fanState:
                self.fanState = action
                logger.info(f'fan,{action}')
                if action:
                    self.message_board.post('Devices', 'VentilationOn')
                    self.lastOff = None
                else:
                    self.message_board.post('Devices', 'VentilationOff')
                    self.lastOff = uptime
