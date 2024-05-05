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
import codecs
import datetime
import os
import shutil
import time

from numpy import isnan, NaN

from ip import get_ip_address, get_wan_ip
from uptime import uptime
from component import Component
from sht75 import SensorData

COLOR_FAN = 'color:#FF8C00'
COLOR_RED = 'color:red'

prog_start = uptime()

DEBUG = False

config = RawConfigParser()
config.read('fancontrol.cfg')
page_filename = config.get('webserver', 'page')
page_filename_temp = config.get('webserver', 'temppage')
data_filename = config.get('webserver', 'data')
data_filename_temp = config.get('webserver', 'tempdata')

index_source = config.get('webserver', 'indexsource')
index_target = config.get('webserver', 'indextarget')
shutil.copyfile(index_source, index_target)


def css_style(x: SensorData) -> SensorData:
    c = SensorData()
    c.rH = '' if isnan(x.humidity) else COLOR_RED
    c.T = '' if isnan(x.temperature) else COLOR_RED
    c.tau = '' if isnan(x.tau) else COLOR_RED
    return c


def pretty_print(number: float) -> str:
    return f'{number:2.1f}'.replace('-', u'−')


class PageGenerator:
    def __init__(self) -> None:
        self.status_txt: str = 'Status: Not set.'
        self.status_style: str = COLOR_RED
        self.set_mode(None)
        self.set_fan_state(None)
        self.last_sync = None
        self.sense1: SensorData = SensorData(temperature=NaN, tau=NaN, humidity=NaN)
        self.sense2: SensorData = SensorData(temperature=NaN, tau=NaN, humidity=NaN)

        self.fan_state_txt: str = 'Fan state: unknown.'
        self.fan_state_style: str = COLOR_RED
        self.mode_txt: str = ''

    def set_measurements(self, sense1: SensorData, sense2: SensorData) -> None:
        self.sense1 = sense1
        self.sense2 = sense2

    def set_status(self, status: tuple[str, str, ...]) -> None:
        self.status_txt = status[0]
        self.status_style = status[1]
        self.last_sync = status[2]

    def set_fan_state(self, state: str | None) -> None:
        match state:
            case 'FanOn':
                self.fan_state_txt = 'Fan: On.'
                self.fan_state_style = COLOR_FAN
            case 'FanOff':
                self.fan_state_txt = 'Fan: Off.'
                self.fan_state_style = ''
            case 'OpenWindow':
                self.fan_state_txt = 'Window is being opened.'
                self.fan_state_style = COLOR_FAN
            case 'CloseWindow':
                self.fan_state_txt = 'Window is being closed.'
                self.fan_state_style = COLOR_FAN
            case _:
                self.fan_state_txt = 'Fan state: unknown.'
                self.fan_state_style = COLOR_RED

    def set_mode(self, mode: str | None) -> None:
        match mode:
            case 'manual':
                self.mode_txt = 'Mode: manual. '
            case _:
                self.mode_txt = ''

    def write(self) -> None:
        localtime = time.localtime()
        with codecs.open(page_filename_temp, 'w', encoding='utf8') as f:
            f.write(f'''<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN">
<html>
<head>
<meta http-equiv="content-type" content="text/html; charset=UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fan control</title>
<meta name="author" content="Daniel Müllner">
<script type="text/JavaScript">
function timedRefresh(timeoutPeriod) {{ setTimeout("location.reload(true);",timeoutPeriod); }}
window.onload = timedRefresh(10000);
</script>
</head>
<style>
body {{font-family: sans-serif;}}
h1 {{font-size: 125%;}}
table {{border:1px solid grey;
border-collapse:collapse;}}
            td{{padding:4px 8px}}
tr.bg {{background-color:#ffb;}}
tr.hr {{border-bottom:1px solid black}}
td.l {{text-align:left;}}
td.c {{text-align:center;}}
td.r {{text-align:right;}}
</style>
<body>
<h1>Fan control</h1>
<table>
  <tr>
    <td colspan="3">
      {time.strftime("%d.%m.%Y", localtime)}<span style="float:right">{time}</span>
    </td>
  </tr>
  <tr class="hr">
    <td>
    </td>
    <td class="c">
      Indoors
    </td>
    <td class="c">
      Outdoors
    </td>
  </tr>
  <tr class="bg">
    <td>
      Relative humidity in %
    </td>
    <td class="c" style="{css_style(self.sense1).humidity}">
      {pretty_print(self.sense1.humidity)}
    </td>
    <td class="c" style="{css_style(self.sense2).humidity}">
      {pretty_print(self.sense2.humidity)}
    </td>
  </tr>
  <tr>
    <td>
      Temperature in °C
    </td>
    <td class="c" style="{css_style(self.sense1).temperature}">
      {pretty_print(self.sense1.temperature)}
    </td>
    <td class="c" style="{css_style(self.sense2).temperature}">
      {pretty_print(self.sense2.temperature)}
    </td>
  </tr>
  <tr class="bg">
    <td>
      Dew point in °C
    </td>
    <td class="c" style="{css_style(self.sense1).tau}">
      {pretty_print(self.sense1.tau)}
    </td>
    <td class="c" style="{css_style(self.sense2).tau}">
      {pretty_print(self.sense2.tau)}
    </td>
  </tr>
  <tr>
    <td colspan="3" style="{self.fan_state_style}">
      {self.mode_txt}{self.fan_state_txt}
    </td>
  </tr>
  <tr class="bg hr">
    <td colspan="3" style="{self.status_style}">
      {self.status_txt}
    </td>
  </tr>
  <tr>
    <td colspan="3">
      IP Ethernet:&nbsp;<span style="float:right">{get_ip_address('eth0')}</span>
    </td>
  </tr>
  <tr class="bg">
    <td colspan="3">
      IP WLAN:&nbsp;<span style="float:right">{get_ip_address('wlan0')}</span>
    </td>
  </tr>
  <tr>
    <td colspan="3">
      IP WAN:&nbsp;<span style="float:right">{get_wan_ip()}</span>
    </td>
  </tr>
  <tr class="bg">
    <td colspan="3">
      OS uptime:&nbsp;<span style="float:right">{str(datetime.timedelta(seconds=int(uptime())))}</span>
    </td>
  </tr>
  <tr>
    <td colspan="3">
      Controller uptime:&nbsp;<span style="float:right">{str(datetime.timedelta(
                seconds=int(uptime() - prog_start)))}</span>
    </td>
  </tr>
  <tr class="bg">
    <td colspan="3">
      Last DCF77 signal:&nbsp;<span style="float:right">{self.last_sync if self.last_sync else 'None'}</span>
    </td>
  </tr>
</table>
</body>
</html>
''')
        os.rename(page_filename_temp, page_filename)

    def write_data(self) -> None:
        localtime = time.localtime()
        with codecs.open(data_filename_temp, 'w', encoding='utf8') as f:
            f.write(f'''\
{time.strftime("%d.%m.%Y", localtime)}
{time.strftime("%H:%M:%S", localtime)}
{css_style(self.sense1).humidity}
{pretty_print(self.sense1.humidity)}
{css_style(self.sense2).humidity}
{pretty_print(self.sense2.humidity)}
{css_style(self.sense1).temperature}
{pretty_print(self.sense1.temperature)}
{css_style(self.sense2).temperature}
{pretty_print(self.sense2.temperature)}
{css_style(self.sense1).tau}
{pretty_print(self.sense1.tau)}
{css_style(self.sense2).tau}
{pretty_print(self.sense2.tau)}
{self.fan_state_style}
{self.mode_txt}{self.fan_state_txt}
{self.status_style}
{self.status_txt}
{get_ip_address('eth0')}
{get_ip_address('wlan0')}
{get_wan_ip()}
{str(datetime.timedelta(seconds=int(uptime())))}
{str(datetime.timedelta(seconds=int(uptime() - prog_start)))}
{self.last_sync if self.last_sync else 'None'}''')
        os.rename(data_filename_temp, data_filename)

    @staticmethod
    def write_end_page() -> None:
        localtime = time.localtime()
        with open(page_filename_temp, 'w') as f:
            f.write(f'''<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN">
<html>
<head>
<meta http-equiv="content-type" content="text/html; charset=UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fan control</title>
<meta name="author" content="Daniel Müllner">
<script type="text/JavaScript">
function timedRefresh(timeoutPeriod) {{ setTimeout("location.reload(true);",timeoutPeriod); }}
window.onload = timedRefresh(10000);
</script>
</head>
<style>
body {{font-family: sans-serif;}}
</style>
<body>
{time.strftime("%d.%m.%Y", localtime)}, {time.strftime("%H:%M:%S", localtime)}: Program exited.
</body>
</html>
''')
        os.rename(page_filename_temp, page_filename)


class HtmlWriter(Component):
    def __init__(self) -> None:
        super().__init__('HTML writer')
        self.pageGenerator = PageGenerator()
        self.status_old = (None, None)

    def __enter__(self) -> object:
        with self.lock:
            self.message_board.subscribe('Measurement', self, HtmlWriter.on_measurement)
            self.message_board.subscribe('HTMLStatus', self, HtmlWriter.on_html_status)
            self.message_board.subscribe('FanState', self, HtmlWriter.on_fan_state)
            self.message_board.subscribe('Mode', self, HtmlWriter.on_mode)
        return super().__enter__()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        super().__exit__(exc_type, exc_value, traceback)
        with self.lock:
            self.pageGenerator.write_end_page()

    def on_measurement(self, message: tuple[str, SensorData, SensorData]):
        with self.lock:
            self.pageGenerator.set_measurements(*message[1:])
            self.pageGenerator.write_data()

    def on_html_status(self, message: tuple[str, str, ...]) -> None:
        with self.lock:
            self.pageGenerator.set_status(message)
            self.pageGenerator.write_data()

    def on_fan_state(self, message: str) -> None:
        with self.lock:
            self.pageGenerator.set_fan_state(message)
            self.pageGenerator.write_data()

    def on_mode(self, message: str) -> None:
        with self.lock:
            self.pageGenerator.set_mode(message)
            self.pageGenerator.write_data()
