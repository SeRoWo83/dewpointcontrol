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

from component import Component
from ip import get_ip_address
from uptime import uptime

logger = logging.getLogger('fancontrol')

config = RawConfigParser()
config.read('fancontrol.cfg')
button_left = config.getint('pins', 'button_left')
button_right = config.getint('pins', 'button_right')
button_front = config.getint('pins', 'button_front')
button_back = config.getint('pins', 'button_back')

GPIO.setmode(GPIO.BOARD)


class ButtonController:
    def __init__(self, messageboard):
        self.messageboard = messageboard
        self.buttons = []

    def __enter__(self) -> object:
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        for button in self.buttons:
            GPIO.remove_event_detect(button)
        GPIO.cleanup(self.buttons)
        del self.buttons

    def addbuttoncallback(self, button, callback):
        self.buttons.append(button)
        print(f'Set up button {button}.')
        GPIO.setup(button, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        def wrapped_callback(*args, **kwargs):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                self.messageboard.post('Exception', e)

        GPIO.add_event_detect(button, GPIO.BOTH, callback=wrapped_callback, bouncetime=100)


class Menu(Component):
    def __init__(self):
        super().__init__('menu')
        self.menus: list[MainScreen] = [MainScreen(self.message_board)]
        self.menus[-1].display()

    def __enter__(self):
        with self.lock:
            self.button_controller = ButtonController(self.message_board)
            self.button_controller.__enter__()
            self.button_controller.addbuttoncallback(button_left, self.cancel)
            self.button_controller.addbuttoncallback(button_back, self.back)
            self.button_controller.addbuttoncallback(button_front, self.forward)
            self.button_controller.addbuttoncallback(button_right, self.select)
        return super().__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        with self.lock:
            self.button_controller.__exit__(exc_type, exc_value, traceback)
        super().__exit__(exc_type, exc_value, traceback)

    def cancel(self, pin):
        with self.lock:
            pressed = not GPIO.input(pin)
            if pressed:
                if len(self.menus) > 1:
                    self.menus.pop().leave()
                    self.menus[-1].display()
            self.wait_until_released(pin)

    def back(self, pin):
        with self.lock:
            pressed = not GPIO.input(pin)
            if pressed:
                new_menu = self.menus[-1].back()
                if new_menu:
                    self.menus.append(new_menu)
                    new_menu.display()
            self.wait_until_released(pin)

    def forward(self, pin):
        with self.lock:
            pressed = not GPIO.input(pin)
            if pressed:
                new_menu = self.menus[-1].forward()
                if new_menu:
                    self.menus.append(new_menu)
                    new_menu.display()
            self.wait_until_released(pin)

    def select(self, pin):
        with self.lock:
            pressed = not GPIO.input(pin)
            if pressed:
                newmenu = self.menus[-1].select(pin)
                if newmenu:
                    self.menus.append(newmenu)
                    newmenu.display()
            self.wait_until_released(pin)

    @staticmethod
    def wait_until_released(pin):
        while not GPIO.input(pin):
            time.sleep(.1)


class MainScreen:
    def __init__(self, messageboard):
        self.messageboard = messageboard

    def display(self):
        self.messageboard.post('MainScreen', True)

    def forward(self):
        return MainMenu(self.messageboard)

    def back(self):
        return MainMenu(self.messageboard)

    def select(self, pin):
        return MainMenu(self.messageboard)

    def leave(self):
        pass


class MainMenu:
    displayLines = 6

    def __init__(self, messageboard):
        self.messageboard = messageboard
        self.items = [u'Info',
                      u'XXX',
                      u'Schliesse Fenster',
                      u'Öffne Fenster',
                      u'Ventilator aus',
                      u'Ventilator an',
                      u'Restart WLAN',
                      u'Herunterfahren']
        self.currentitem = 0
        self.firstline = 0
        self.status = ''

    def display(self):
        mode = self.messageboard.query('Mode')
        if mode == 'manual':
            self.items[1] = u'Modus: manuell'
        else:
            self.items[1] = u'Modus: Automatik'
        self.messageboard.post('Menu', (self.items[self.firstline: self.firstline + self.displayLines],
                                        self.currentitem - self.firstline,
                                        self.status))

    def forward(self):
        if self.currentitem < len(self.items) - 1:
            self.currentitem += 1
            if self.currentitem + self.firstline >= self.displayLines:
                self.firstline += 1
            self.display()

    def back(self):
        if self.currentitem > 0:
            self.currentitem -= 1
            if self.currentitem < self.firstline:
                self.firstline -= 1
            self.display()

    def select(self, pin):
        if self.currentitem == 0:
            self.status = ''
            return InfoScreen(self.messageboard)
        elif self.currentitem == 1:
            self.status = ''
            mode = self.messageboard.query('Mode')
            if mode == 'manual':
                mode = 'auto'
            else:
                mode = 'manual'
            self.messageboard.post('Mode', mode)
            self.display()
            logger.info(f'user,Mode:{mode}')
        elif self.currentitem == 2:
            self.status = u'Schliesse Fenster…'
            self.messageboard.post('Mode', 'manual')
            self.display()
            logger.info('user,CloseWindow')
            self.messageboard.post('Devices', 'StartCloseWindow')
            while not GPIO.input(pin):
                time.sleep(.1)
            self.messageboard.post('Devices', 'StopWindowMotor')
            self.status = u'Fensteröffner ist aus.'
            self.display()
        elif self.currentitem == 3:
            self.status = u'Öffne Fenster…'
            self.messageboard.post('Mode', 'manual')
            self.display()
            logger.info('user,OpenWindow')
            self.messageboard.post('Devices', 'StartOpenWindow')
            while not GPIO.input(pin):
                time.sleep(.1)
            self.messageboard.post('Devices', 'StopWindowMotor')
            self.status = u'Fensteröffner ist aus.'
            self.display()
        elif self.currentitem == 4:
            self.messageboard.post('Mode', 'manual')
            self.messageboard.post('Devices', 'FanOff')
            self.status = u'Ventilator ist aus.'
            self.display()
            logger.info('user,FanOff')
        elif self.currentitem == 5:
            self.messageboard.post('Mode', 'manual')
            self.messageboard.post('Devices', 'FanOn')
            self.status = u'Ventilator ist an.'
            self.display()
            logger.info('user,FanOn')
        elif self.currentitem == 6:
            self.status = u'Restart WLAN…'
            self.display()
            self.messageboard.post('RestartWLAN', True)
            self.display()
        elif self.currentitem == 7:
            self.status = u'Herunterfahren…'
            self.display()
            self.messageboard.post('Shutdown', True)

    def leave(self):
        pass


prefix = [(float(1 << e), p) for e, p in ((30, 'G'), (20, 'M'), (10, 'K'))]


def humanBytes(n):
    for m, p in prefix:
        if n >= m:
            return f'{(n / m):.1f}{p}'
    return f"{n}B"


def getAvailableRAM():
    return humanBytes(psutil.virtual_memory().available)


class InfoScreen:
    prog_start = uptime()
    display_lines = 7

    def __init__(self, messageboard) -> None:
        self.messageboard = messageboard
        self.index = 0

    def display(self) -> None:
        infolines = (
            ['IP Ethernet/WLAN:'],
            ['', get_ip_address('eth0')],
            ['', get_ip_address('wlan0')],
            ['Bootvorgang vor:'],
            ['', str(datetime.timedelta(seconds=int(uptime())))],
            ['Programmstart vor:'],
            ['', str(datetime.timedelta(seconds=int(uptime() - self.prog_start)))],
            ['Freies RAM:', getAvailableRAM()],
        )
        self.index = max(min(self.index, len(infolines) - self.display_lines), 0)
        self.messageboard.post(
            'Info',
            infolines[self.index:self.index + self.display_lines])

    def forward(self) -> None:
        self.index += 1
        self.display()

    def back(self) -> None:
        self.index -= 1
        self.display()

    def select(self, pin):
        pass

    def leave(self) -> None:
        pass
