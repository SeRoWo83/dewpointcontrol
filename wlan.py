#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Copyright © 2016 Daniel Müllner <https://danifold.net>

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

from time import struct_time
from configparser import RawConfigParser
from datetime import datetime
import logging
from threading import Event

import dbus

from component import Component, ComponentWithThread
from uptime import uptime
from ip import get_ip_address

from misc import CSV, delay

DEBUG = False

logger = logging.getLogger('fancontrol')

config = RawConfigParser()
config.read('fancontrol.cfg')

measure_interval = config.getint('check_network', 'interval')
assert measure_interval >= 1


class RestartWLAN(Component):
    def __init__(self) -> None:
        super().__init__('restartWLAN')

    def __enter__(self) -> object:
        with self.lock:
            self.message_board.subscribe('RestartWLAN', self, RestartWLAN.on_reset_wlan)
        return super().__enter__()

    def on_reset_wlan(self, message: bool) -> None:
        assert message is True
        with self.lock:
            sys_bus = dbus.SystemBus()
            systemd1 = sys_bus.get_object('org.freedesktop.systemd1', '/org/freedesktop/systemd1')
            manager = dbus.Interface(systemd1, 'org.freedesktop.systemd1.Manager')
            job = manager.RestartUnit('netctl@ts3.service', 'fail')


class CheckNetwork(ComponentWithThread):
    def __init__(self) -> None:
        super().__init__('check_wlan')
        self.event: Event = Event()
        ut: float = uptime()
        self.last_measurement: float = ut
        self.uptime: float = ut

    def __enter__(self) -> object:
        self.message_board.subscribe('Time', self, CheckNetwork.on_time)
        return super().__enter__()

    def on_time(self, message: tuple[float, struct_time]) -> None:
        self.uptime, _ = message
        if self.uptime > self.last_measurement + 10.5:
            logger.warning(f'Interval between network checks > 10.5s: {self.last_measurement}, {self.uptime}.')
        if int(self.uptime) % measure_interval == 0 or self.uptime > self.last_measurement + 10.5:
            self.last_measurement = self.uptime
            self.event.set()

    @staticmethod
    def check_network() -> bool:
        return get_ip_address('wlan0') != 'None' or get_ip_address('eth0') != 'None'

    def run(self) -> None:
        while self.message_board.query('ExitThread') is None:
            if self.event.wait(1):
                self.event.clear()
                # Start measurement approx. 250 ms after the full second.
                # This lowers interference with the DCF77 receiver.
                microsecond = datetime.now().microsecond
                wait = ((1500000 - microsecond) % 1000000) / 1000000.0
                assert wait >= 0
                assert wait < 1
                delay(wait)
                online = self.check_network()
                self.message_board.post('Network', online)
                # logger.info(CSV('network', online))
