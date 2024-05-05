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

import atexit
from configparser import RawConfigParser
from queue import Queue, Empty

import RPi.GPIO as GPIO

from misc import delay
from component import ComponentWithThread

DEBUG = False
CLOSE_WINDOW = True

config = RawConfigParser()
config.read('fancontrol.cfg')
relays = [
    config.getint('pins', 'relay1'),
    config.getint('pins', 'relay2'),
    config.getint('pins', 'relay3'),
    config.getint('pins', 'relay4')]


def cleanup() -> None:
    print('Start GPIO cleanup for devices.')
    GPIO.output(relays, GPIO.HIGH)
    GPIO.cleanup(relays)
    print('GPIO cleaned up for devices.')


atexit.register(cleanup)

GPIO.setmode(GPIO.BOARD)
for relay in relays:
    print(f'Set up relay on port {relay}.')
    GPIO.setup(relay, GPIO.OUT, initial=GPIO.HIGH)


class Devices(ComponentWithThread):
    def __init__(self) -> None:
        super().__init__('devices')
        self.isFanOn = False
        self.isWindowMotorOn = False
        self.queue = Queue()
        if CLOSE_WINDOW:
            self.on_devices('VentilationOff')

    def __enter__(self) -> object:
        with self.lock:
            self.message_board.subscribe('Devices', self, Devices.on_devices)
        return super().__enter__()

    def stop(self) -> None:
        super().stop()
        if CLOSE_WINDOW:
            self.__fan_off()
            self.__close_window()

    def on_devices(self, message: str) -> None:
        with self.lock:
            self.queue.put(message)

    def run(self) -> None:
        while self.message_board.query('ExitThread') is None:
            try:
                if DEBUG:
                    print(f'Devices: queue length is {self.queue.qsize()}')
                message = self.queue.get(True, 1)
                self.queue.task_done()
                if DEBUG:
                    print(f'Devices message: {message}')

                match message:
                    case 'StartOpenWindow':
                        self.__start_open_window()
                    case 'StartCloseWindow':
                        self.__start_close_window()
                    case 'StopWindowMotor':
                        self.__stop_window_motor()
                    case 'OpenWindow':
                        self.__open_window()
                    case 'CloseWindow':
                        self.__close_window()
                    case 'FanOn':
                        self.__fan_on()
                    case 'FanOff':
                        self.__fan_off()
                    case 'VentilationOn':
                        self.__open_window(), self.__fan_on()
                    case 'VentilationOff':
                        self.__fan_off(), self.__close_window()
                    case _:
                        raise ValueError(message)
            except Empty:
                pass

    def __start_open_window(self) -> None:
        if self.isWindowMotorOn:
            self.__stop_window_motor()
        self.message_board.post('FanState', 'OpenWindow')
        self.isWindowMotorOn = True
        GPIO.output(relays[1], GPIO.LOW)
        delay(.5)
        GPIO.output([relays[0], relays[3]], GPIO.LOW)
        delay(.5)

    def __start_close_window(self) -> None:
        if self.isWindowMotorOn:
            self.__stop_window_motor()
        self.message_board.post('FanState', 'CloseWindow')
        self.isWindowMotorOn = True
        GPIO.output(relays[1], GPIO.HIGH)
        delay(.5)
        GPIO.output([relays[0], relays[3]], GPIO.LOW)
        delay(.5)

    def __stop_window_motor(self) -> None:
        if self.isFanOn:
            self.message_board.post('FanState', 'FanOn')
        else:
            self.message_board.post('FanState', 'FanOff')
        GPIO.output(relays[0], GPIO.HIGH)
        delay(.5)
        GPIO.output(relays[1], GPIO.HIGH)
        self.isWindowMotorOn = False
        if not self.isFanOn:
            GPIO.output(relays[3], GPIO.HIGH)
        delay(.5)

    def __open_window(self) -> None:
        self.__start_open_window()
        delay(10)
        self.__stop_window_motor()

    def __close_window(self) -> None:
        self.__start_close_window()
        delay(10)
        self.__stop_window_motor()

    def __fan_on(self) -> None:
        self.message_board.post('FanState', 'FanOn')
        GPIO.output(relays[2:4], GPIO.LOW)
        self.isFanOn = True
        delay(.5)

    def __fan_off(self) -> None:
        GPIO.output(relays[2], GPIO.HIGH)
        self.isFanOn = False
        if not self.isWindowMotorOn:
            GPIO.output(relays[3], GPIO.HIGH)
            self.message_board.post('FanState', 'FanOff')
        delay(.5)
