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

from configparser import RawConfigParser
import datetime
import logging
import psutil
import RPi.GPIO as GPIO
import time
from typing import Self, Callable, Any

from component import Component
from ip import get_ip_address
from uptime import uptime
from messageboard import MessageBoard

logger = logging.getLogger('fancontrol')

config = RawConfigParser()
config.read('fancontrol.cfg')
button_left = config.getint('pins', 'button_left')
button_right = config.getint('pins', 'button_right')
button_front = config.getint('pins', 'button_front')
button_back = config.getint('pins', 'button_back')

GPIO.setmode(GPIO.BOARD)


class ButtonController:
    def __init__(self, message_board: MessageBoard) -> None:
        self.message_board = message_board
        self.buttons = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        for button in self.buttons:
            GPIO.remove_event_detect(button)
        GPIO.cleanup(self.buttons)
        del self.buttons

    def add_button_callback(self, button: int, callback: Callable[[int], None]) -> None:
        self.buttons.append(button)
        print(f'Set up button {button}.')
        GPIO.setup(button, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        def wrapped_callback(*args: tuple, **kwargs: dict[str, Any]):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                self.message_board.post('Exception', e)

        GPIO.add_event_detect(button, GPIO.BOTH, callback=wrapped_callback, bouncetime=100)


class Menu(Component):
    def __init__(self) -> None:
        super().__init__('menu')
        self.menus: list[MainScreen | MainMenu] = [MainScreen(self.message_board)]
        self.menus[-1].display()

    def __enter__(self) -> Self:
        with self.lock:
            self.button_controller = ButtonController(self.message_board)
            self.button_controller.__enter__()
            self.button_controller.add_button_callback(button_left, self.cancel)
            self.button_controller.add_button_callback(button_back, self.back)
            self.button_controller.add_button_callback(button_front, self.forward)
            self.button_controller.add_button_callback(button_right, self.select)
        return super().__enter__()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        with self.lock:
            self.button_controller.__exit__(exc_type, exc_value, traceback)
        super().__exit__(exc_type, exc_value, traceback)

    def cancel(self, pin: int) -> None:
        with self.lock:
            pressed = not GPIO.input(pin)
            if pressed and len(self.menus) > 1:
                self.menus.pop().leave()
                self.menus[-1].display()
            self.wait_until_released(pin)

    def back(self, pin: int) -> None:
        with self.lock:
            pressed = not GPIO.input(pin)
            if pressed:
                new_menu = self.menus[-1].back()
                if new_menu:
                    self.menus.append(new_menu)
                    new_menu.display()
            self.wait_until_released(pin)

    def forward(self, pin: int) -> None:
        with self.lock:
            pressed = not GPIO.input(pin)
            if pressed:
                new_menu = self.menus[-1].forward()
                if new_menu:
                    self.menus.append(new_menu)
                    new_menu.display()
            self.wait_until_released(pin)

    def select(self, pin: int) -> None:
        with self.lock:
            pressed = not GPIO.input(pin)
            if pressed:
                new_menu = self.menus[-1].select(pin)
                if new_menu:
                    self.menus.append(new_menu)
                    new_menu.display()
            self.wait_until_released(pin)

    @staticmethod
    def wait_until_released(pin: int) -> None:
        while not GPIO.input(pin):
            time.sleep(.1)


class InfoScreen:
    prog_start = uptime()
    display_lines = 7

    def __init__(self, message_board: MessageBoard) -> None:
        self.message_board = message_board
        self.index = 0

    def display(self) -> None:
        info_lines = (
            ['IP Ethernet/WLAN:'],
            ['', get_ip_address('eth0')],
            ['', get_ip_address('wlan0')],
            ['Bootvorgang vor:'],
            ['', str(datetime.timedelta(seconds=int(uptime())))],
            ['Programmstart vor:'],
            ['', str(datetime.timedelta(seconds=int(uptime() - self.prog_start)))],
            ['Freies RAM:', get_available_ram()],
        )
        self.index = max(min(self.index, len(info_lines) - self.display_lines), 0)
        self.message_board.post(
            'Info',
            info_lines[self.index:self.index + self.display_lines])

    def forward(self) -> None:
        self.index += 1
        self.display()

    def back(self) -> None:
        self.index -= 1
        self.display()

    def select(self, pin: int) -> None:
        # Dummy
        pass

    def leave(self) -> None:
        # Dummy
        pass


class MainMenu:
    display_lines = 6

    def __init__(self, message_board: MessageBoard) -> None:
        self.message_board = message_board
        self.items = [u'Info',
                      u'XXX',
                      u'Schliesse Fenster',
                      u'Öffne Fenster',
                      u'Ventilator aus',
                      u'Ventilator an',
                      u'Restart WLAN',
                      u'Herunterfahren']
        self.current_item = 0
        self.first_line = 0
        self.status = ''

    def display(self) -> None:
        mode = self.message_board.query('Mode')
        if mode == 'manual':
            self.items[1] = u'Modus: manuell'
        else:
            self.items[1] = u'Modus: Automatik'
        self.message_board.post('Menu', (self.items[self.first_line: self.first_line + self.display_lines],
                                         self.current_item - self.first_line,
                                         self.status))

    def forward(self) -> None:
        if self.current_item < len(self.items) - 1:
            self.current_item += 1
            if self.current_item + self.first_line >= self.display_lines:
                self.first_line += 1
            self.display()

    def back(self) -> None:
        if self.current_item > 0:
            self.current_item -= 1
            if self.current_item < self.first_line:
                self.first_line -= 1
            self.display()

    def select(self, pin: int) -> InfoScreen | None:
        match self.current_item:
            case 0:
                self.status = ''
                return InfoScreen(self.message_board)
            case 1:
                self.status = ''
                mode = self.message_board.query('Mode')
                if mode == 'manual':
                    mode = 'auto'
                else:
                    mode = 'manual'
                self.message_board.post('Mode', mode)
                self.display()
                logger.info(f'user,Mode:{mode}')
            case 2:
                self.status = u'Schliesse Fenster…'
                self.message_board.post('Mode', 'manual')
                self.display()
                logger.info('user,CloseWindow')
                self.message_board.post('Devices', 'StartCloseWindow')
                while not GPIO.input(pin):
                    time.sleep(.1)
                self.message_board.post('Devices', 'StopWindowMotor')
                self.status = u'Fensteröffner ist aus.'
                self.display()
            case 3:
                self.status = u'Öffne Fenster…'
                self.message_board.post('Mode', 'manual')
                self.display()
                logger.info('user,OpenWindow')
                self.message_board.post('Devices', 'StartOpenWindow')
                while not GPIO.input(pin):
                    time.sleep(.1)
                self.message_board.post('Devices', 'StopWindowMotor')
                self.status = u'Fensteröffner ist aus.'
                self.display()
            case 4:
                self.message_board.post('Mode', 'manual')
                self.message_board.post('Devices', 'FanOff')
                self.status = u'Ventilator ist aus.'
                self.display()
                logger.info('user,FanOff')
            case 5:
                self.message_board.post('Mode', 'manual')
                self.message_board.post('Devices', 'FanOn')
                self.status = u'Ventilator ist an.'
                self.display()
                logger.info('user,FanOn')
            case 6:
                self.status = u'Restart WLAN…'
                self.display()
                self.message_board.post('RestartWLAN', True)
                self.display()
            case 7:
                self.status = u'Herunterfahren…'
                self.display()
                self.message_board.post('Shutdown', True)

    def leave(self) -> None:
        # Dummy
        pass


class MainScreen:
    def __init__(self, message_board: MessageBoard) -> None:
        self.message_board = message_board

    def display(self) -> None:
        self.message_board.post('MainScreen', True)

    def forward(self) -> MainMenu:
        return MainMenu(self.message_board)

    def back(self) -> MainMenu:
        return MainMenu(self.message_board)

    def select(self, _pin: int) -> MainMenu:
        return MainMenu(self.message_board)

    def leave(self) -> None:
        # Dummy
        pass


prefix = [(float(1 << e), p) for e, p in ((30, 'G'), (20, 'M'), (10, 'K'))]


def human_bytes(n: int) -> str:
    for m, p in prefix:
        if n >= m:
            return f'{(n / m):.1f}{p}B'
    return f"{n}B"


def get_available_ram() -> str:
    return human_bytes(psutil.virtual_memory().available)


if __name__ == '__main__':
    print(get_available_ram())
