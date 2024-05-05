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
from time import struct_time
from dataclasses import dataclass

from configparser import RawConfigParser
import os
import pygame
import shutil
import time
from itertools import count
from numpy import NaN

from component import Component
from messageboard import MessageBoard

DEBUG = False

os.environ["SDL_FBDEV"] = "/dev/fb1"
os.environ['SDL_VIDEODRIVER'] = "fbcon"

fontname = 'Droid Sans'

fontsize = 15

config = RawConfigParser()
config.read('fancontrol.cfg')
endscreen_raw = config.get('screenshot', 'endscreen_raw')


def display_end_screen() -> None:
    pygame.quit()
    shutil.copyfile(endscreen_raw, '/dev/fb1')


atexit.register(display_end_screen)

WHITE = (255, 255, 255)
YELLOW = (255, 255, 140)
STATUSBG = (230, 230, 230)

icon_offline = pygame.image.load('/usr/share/icons/HighContrast/16x16/status/network-error.png')
icon_online = pygame.image.load('/usr/share/icons/HighContrast/16x16/status/network-idle.png')
icon_unknown = pygame.image.load('/usr/share/icons/HighContrast/16x16/status/network-no-route.png')


@dataclass
class SensorData:
    humidity: float = NaN
    temperature: float = NaN
    tau: float = NaN
    error: bool = False


class Screen:
    def __init__(self, message_board: MessageBoard) -> None:
        self.message_board = message_board
        pygame.display.init()
        pygame.font.init()
        pygame.mouse.set_visible(0)
        self.line = []
        sizes = pygame.display.list_modes()
        print("Available display sizes:", sizes)
        size = self.width, self.height = sizes[0]
        print('Initialize display...')
        self.screen = pygame.display.set_mode(size)
        print('Done.')
        self.font = pygame.font.SysFont(fontname, fontsize)
        self.clear()
        dummy_measurement = SensorData()
        self.set_measurements(dummy_measurement, dummy_measurement)
        self.set_background(WHITE)
        self.in_menu = True  # Suppress display update
        self.localtime = time.localtime()
        self.in_menu = False

    def clear(self) -> None:
        self.screen.fill((255, 255, 255))
        self.y = 0
        self.lineheight = 0

    def set_background(self, color: tuple[int, int, int]) -> None:
        self.bgcolor = color

    def displaytext(self, text, align, color):
        text = self.font.render(text, True, color, self.bgcolor)
        textpos = text.get_rect()
        textpos.top = self.y
        match align:
            case 'l':
                textpos.left = 2
            case 'r':
                textpos.right = self.width - 2
            case 'c2':
                textpos.centerx = self.width * .5
            case 'c3':
                textpos.centerx = self.width * .82
            case _:
                raise ValueError()
        self.line.append((text, textpos))
        self.lineheight = max(self.lineheight, textpos.height)

    def hrule(self) -> None:
        pygame.draw.line(self.screen, (0, 0, 0), (0, self.y), (self.width - 1, self.y))
        self.y += 1

    def linefeed(self) -> None:
        self.screen.fill(self.bgcolor, pygame.Rect(0, self.y, self.width, self.lineheight))
        for surface, pos in self.line:
            self.screen.blit(surface, pos)
        self.line = []
        self.y += self.lineheight
        self.lineheight = 0
        self.set_background(WHITE)

    def displaybottom(self, text, color):
        text = self.font.render(text, True, color, self.bgcolor)
        textpos = text.get_rect()
        textpos.bottom = self.height
        textpos.left = 2
        self.screen.fill(self.bgcolor, pygame.Rect(0, textpos.top, self.width, self.height - textpos.top))
        self.screen.blit(text, textpos)

    @staticmethod
    def show_page() -> None:
        pygame.display.flip()

    def set_time(self, localtime: struct_time) -> None:
        self.localtime = localtime
        if not self.in_menu:
            self.show_measurements()
        self.message_board.post('StatusProcessed', True)

    def set_measurements(self, sensor1: SensorData, sensor2: SensorData):
        self.rH1 = sensor1.humidity
        self.T1 = sensor1.temperature
        self.tau1 = sensor1.tau
        self.rH2 = sensor2.humidity
        self.T2 = sensor2.temperature
        self.tau2 = sensor2.tau

    def get_fanstate(self) -> tuple[str, tuple[int, int, int]]:
        fanstate = self.message_board.query('FanState')
        match fanstate:
            case 'FanOn':
                return u'Lüftung ist an.', (255, 127, 0)
            case 'FanOff':
                return u'Lüftung ist aus.', (0, 127, 0)
            case 'OpenWindow':
                return u'Öffne Fenster.', (255, 127, 0)
            case 'CloseWindow':
                return u'Schliesse Fenster.', (255, 127, 0)
            case _:
                return u'Lüftung: unbekannt.', (255, 0, 0)

    @staticmethod
    def color(x: float) -> tuple[int, int, int]:
        return (0, 0, 0) if x == x else (255, 0, 0)

    def show_measurements(self):
        self.clear()
        self.displaytext(time.strftime("%d.%m.%Y", self.localtime), 'l', (0, 0, 0))
        self.displaytext(time.strftime("%H:%M:%S", self.localtime), 'r', (0, 0, 0))
        self.linefeed()
        self.displaytext("Innen", 'c2', (0, 0, 0))
        self.displaytext("Aussen", 'c3', (0, 0, 0))
        self.linefeed()
        self.hrule()
        self.set_background(YELLOW)
        self.displaytext("rF in %", 'l', (0, 0, 0))
        self.displaytext(f'{self.rH1:2.1f}', 'c2', self.color(self.rH1))
        self.displaytext(f'{self.rH2:2.1f}', 'c3', self.color(self.rH2))
        self.linefeed()
        self.displaytext(u"T in °C", 'l', (0, 0, 0))
        self.displaytext(f'{self.T1:2.1f}', 'c2', self.color(self.T1))
        self.displaytext(f'{self.T2:2.1f}', 'c3', self.color(self.T2))
        self.linefeed()
        self.set_background(YELLOW)
        self.displaytext(u"τ in °C", 'l', (0, 0, 0))
        self.displaytext(f'{self.tau1:2.1f}', 'c2', self.color(self.tau1))
        self.displaytext(f'{self.tau2:2.1f}', 'c3', self.color(self.tau2))
        self.linefeed()
        fanstatetext, fanstatecolor = self.get_fanstate()
        self.displaytext(fanstatetext, 'l', fanstatecolor)
        online = self.message_board.query('Network')
        if online is None:
            icon = icon_unknown
        elif online:
            icon = icon_online
        else:
            icon = icon_offline
        iconpos = icon.get_rect()
        iconpos.top = self.y
        iconpos.right = self.width
        self.line.append((icon, iconpos))
        self.linefeed()
        status = self.message_board.query('Status')
        if status is not None:
            statustxt, statuscolor = status
            self.displaytext(statustxt, 'l', statuscolor)
            self.linefeed()
        self.show_page()

    def show_startscreen(self):
        self.clear()
        self.displaytext('Fan control', 'l', (0, 0, 0))
        self.linefeed()
        self.displaytext(u'by Daniel Müllner', 'l', (0, 0, 0))
        self.linefeed()
        self.show_page()

    def leave_menu(self) -> None:
        self.in_menu = False
        self.show_measurements()

    def show_menu(self, items, highlight=None, statusline=None):
        self.in_menu = True
        self.clear()
        for index, item in zip(count(), items):
            if index == highlight:
                self.set_background((127, 255, 127))
            self.displaytext(item, 'l', (0, 0, 0))
            self.linefeed()
        if statusline:
            self.set_background(STATUSBG)
            self.displaybottom(statusline, (50, 50, 255))
            self.set_background(WHITE)
        self.show_page()

    def show_info(self, items, highlight=None, statusline=None):
        self.in_menu = True
        self.clear()
        for index, item in zip(count(), items):
            if index == highlight:
                self.set_background((127, 255, 127))
            self.displaytext(item[0], 'l', (0, 0, 0))
            if len(item) > 1:
                self.displaytext(item[1], 'r', (0, 0, 0))
            self.linefeed()
        if statusline:
            self.set_background(STATUSBG)
            self.displaybottom(statusline, (50, 50, 255))
            self.set_background(WHITE)
        self.show_page()


class Display(Component):
    def __init__(self) -> None:
        super().__init__('display')
        self.screen = Screen(self.message_board)
        self.screen.show_startscreen()

    def __enter__(self) -> object:
        with self.lock:
            self.message_board.subscribe('Measurement', self, Display.on_measurement)
            self.message_board.subscribe('Time', self, Display.on_time)
            self.message_board.subscribe('MainScreen', self, Display.on_main_screen)
            self.message_board.subscribe('Menu', self, Display.on_menu)
            self.message_board.subscribe('Info', self, Display.on_info)
        return super().__enter__()

    def on_measurement(self, message: tuple[float, struct_time]) -> None:
        with self.lock:
            self.screen.set_measurements(*message[1:])

    def on_time(self, message: tuple[float, struct_time]) -> None:
        _, localtime = message
        with self.lock:
            self.screen.set_time(localtime)

    def on_main_screen(self, _: tuple[float, struct_time]) -> None:
        with self.lock:
            self.screen.leave_menu()

    def on_menu(self, message: tuple[float, struct_time]) -> None:
        with self.lock:
            self.screen.show_menu(*message)

    def on_info(self, message: tuple[float, struct_time]) -> None:
        with self.lock:
            self.screen.show_info(message)
