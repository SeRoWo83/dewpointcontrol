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

import sys

from configparser import RawConfigParser
from lxml import etree
import os
import shutil
import subprocess
import tempfile
import time
import datetime
from datetime import date as date_t
import numpy as np
import calendar

config = RawConfigParser()
config.read('fancontrol.cfg')

w, h = 1440, 600  # graph size
w_plus = w + 85  # image size
h_plus = h + 75

intervals = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 200, 300, 600]  # divisors of h

today = datetime.date.today()


def next_off_time(date: date_t, start_timestamp: float) -> float | None:
    date = date + datetime.timedelta(days=1)
    logfile = config.get('logging', 'logfile')
    if date != today:
        logfile += date.strftime('.%Y-%m-%d')

    if os.path.isfile(logfile):
        for line in open(logfile, 'r'):
            entries = [entry.strip() for entry in line.split(',')]
            t = time.strptime(entries[0], '%Y-%m-%d %H:%M:%S')
            timestamp: int = calendar.timegm(t)
            minute = int(np.floor((timestamp - start_timestamp) / 60))
            assert minute >= w, (minute, w)
            match entries[4:7]:
                case['fan.py', 'fan', 'True']:
                    return
                case['fan.py', 'fan', 'False']:
                    return timestamp
                case['menu.py', 'user', 'FanOn']:
                    return
                case['menu.py', 'user', 'FanOff']:
                    return timestamp
                case['control.py', 'Startup' | 'Shutdown', *_]:
                    return timestamp
    return time.time()


def last_on_time(date: date_t, start_timestamp: float) -> float | None:
    date = date + datetime.timedelta(days=-1)
    logfile = config.get('logging', 'logfile')
    if date != today:
        logfile += date.strftime('.%Y-%m-%d')

    last_on_timestamp = None

    if os.path.isfile(logfile):
        for line in open(logfile, 'r'):
            entries = [entry.strip() for entry in line.split(',')]
            t = time.strptime(entries[0], '%Y-%m-%d %H:%M:%S')
            timestamp = calendar.timegm(t)
            minute = int(np.floor((timestamp - start_timestamp) / 60))
            assert minute < 0
            match entries[4:7]:
                case['fan.py', 'fan', 'True']:
                    last_on_timestamp = timestamp
                case['fan.py', 'fan', 'False']:
                    last_on_timestamp = None
                case['menu.py', 'user', 'FanOn']:
                    last_on_timestamp = timestamp
                case['menu.py', 'user', 'FanOff']:
                    last_on_timestamp = None
                case['control.py', 'Startup' | 'Shutdown', *_]:
                    last_on_timestamp = None
    return last_on_timestamp


def read_log(*date: tuple[int, int, int]) -> tuple[..., ..., float, float, ...]:
    date = datetime.date(*date)
    logfile = config.get('logging', 'logfile')
    if date != today:
        logfile += date.strftime('.%Y-%m-%d')

    t = date.timetuple()
    start_timestamp: float = time.mktime(t)

    on_times = []
    off_times = []
    extra_off_times = [time.time()]
    data1 = np.zeros((w, 2))
    data2 = np.zeros((w, 2))
    num1 = np.zeros((w, 1), dtype=int)
    num2 = np.zeros((w, 1), dtype=int)

    min_temperature = np.infty
    max_temperature = -min_temperature

    for line in open(logfile, 'r'):
        entries = [entry.strip() for entry in line.split(',')]
        t = time.strptime(entries[0], '%Y-%m-%d %H:%M:%S')
        timestamp = calendar.timegm(t)
        minute = int(np.floor((timestamp - start_timestamp) / 60))
        assert minute >= 0
        assert minute < w + 60
        if minute >= w:
            continue
        match entries[4:7]:
            case['fan.py', 'fan', 'True']:
                on_times.append(timestamp)
            case['fan.py', 'fan', 'False']:
                off_times.append(timestamp)
            case['control.py', 'Startup' | 'Shutdown', *_]:
                extra_off_times.append(timestamp)
            case['menu.py', 'user', 'FanOn']:
                on_times.append(timestamp)
            case['menu.py', 'user', 'FanOff']:
                off_times.append(timestamp)
            case['sensor.py', 'measurement', *_]:
                if 0 <= minute <= w:
                    _, temperature1, dewpoint1, error1, _, temperature2, dewpoint2, error2 = entries[6:]
                    if error1 == 'False':
                        temperature1 = float(temperature1)
                        dewpoint1 = float(dewpoint1)
                        data1[minute] += (temperature1, dewpoint1)
                        num1[minute] += 1
                    if error2 == 'False':
                        temperature2 = float(temperature2)
                        dewpoint2 = float(dewpoint2)
                        data2[minute] += (temperature2, dewpoint2)
                        num2[minute] += 1
    # Prevent "RuntimeWarning: invalid value encountered in true_divide"
    data1 = np.where(num1 > 0, data1, np.nan) / num1
    data2 = np.where(num2 > 0, data2, np.nan) / num2

    min_temperature = np.nanmin([np.nanmin(data1), np.nanmin(data2)])
    max_temperature = np.nanmax([np.nanmax(data1), np.nanmax(data2)])

    extra_on_time = last_on_time(date, start_timestamp)
    if extra_on_time is not None:
        on_times.append(extra_on_time)
    extra_off_time = next_off_time(date, start_timestamp)
    if extra_off_time is not None:
        off_times.append(extra_off_time)
    on_times.sort()
    off_times.sort()

    fan_intervals = []
    for on_time in on_times:
        off_index = np.searchsorted(off_times, on_time)
        if off_index < len(off_times):
            off_time = off_times[off_index]
            assert on_time <= off_time, (on_time, off_time)

            x1 = int(np.floor((on_time - start_timestamp) / 60.0))
            if x1 >= w:
                continue
            x1 = max(0, x1)
            x2 = int(np.ceil((off_time - start_timestamp) / 60.0))
            if x2 < 0:
                continue
            x2 = min(x2, w - 1)

            fan_intervals.append((x1, x2))
    return data1, data2, min_temperature, max_temperature, fan_intervals


def plotcurve(subelement, elem, points, _max_temperature, _min_temperature, color):
    if points:
        s = ''
        for x, y in points:
            assert 0 <= x < w
            s += f' {x},{y:.1f}'.rstrip('0').rstrip('.')
        subelement(elem, 'polyline', points=s[1:], style="stroke:" + color)


def plot(subelement, elem, data, max_temperature, min_temperature, color):
    points = []
    for x, T in enumerate(data):
        assert 0 <= x < w
        if T != T:
            plotcurve(subelement, elem, points, max_temperature, min_temperature, color)
            points = []
        else:
            y = (max_temperature - T) / float(max_temperature - min_temperature) * h
            points.append((x, y))
    plotcurve(subelement, elem, points, max_temperature, min_temperature, color)


def make_plot(date: date_t, upload: bool = False, mark_end: bool = False) -> None:
    print(f"Make plot for {date}.")
    year = date.year
    month = date.month
    day = date.day

    data1, data2, min_temperature, max_temperature, fan_intervals = read_log(year, month, day)

    min_temperature_f = min_temperature
    max_temperature_f = max_temperature

    min_temperature = int(np.floor(min_temperature))
    max_temperature = int(np.ceil(max_temperature))

    span_temperature = max_temperature - min_temperature
    for dt in intervals:
        if dt > span_temperature:
            span_temperature = dt
            break

    min_temperature = min(min_temperature,
                          int(np.round((min_temperature_f + max_temperature_f - span_temperature) * .5)))
    max_temperature = min_temperature + span_temperature

    T1color = np.array([0, 0, 255], dtype=np.uint8)
    tau1color = np.array([0, 127, 0], dtype=np.uint8)
    T2color = np.array([255, 0, 0], dtype=np.uint8)
    tau2color = np.array([255, 0, 255], dtype=np.uint8)

    temp_dirname = None
    try:
        svg = etree.Element('svg',
                            nsmap={None: 'https://www.w3.org/2000/svg',
                                   'xlink': 'https://www.w3.org/1999/xlink'},
                            width=f"{w_plus}px",
                            height=f"{h_plus}px",
                            viewBox=f"0 0 {w_plus} {h_plus}",
                            version="1.1")

        style = etree.SubElement(svg, 'style', type="text/css")
        style.text = etree.CDATA('''\
*{fill:none;stroke-width:1px;stroke-linecap:butt;stroke-linejoin:round;}\
line{stroke:black;}\
polyline{stroke-linecap:round;}\
text,tspan{stroke:none;fill:black;font-family:sans-serif;font-size:13px;}\
g.ylabel text{dominant-baseline:mathematical;text-anchor:end;}\
rect{fill:rgb(180,180,180)}\
.thin line{stroke-width:.1px}\
line.thicker{stroke-width:.25px}''')

        defs = etree.SubElement(svg, 'defs')
        my_subelement = etree.SubElement
        my_subelement(defs, 'line', id="htick", x1="0", y1="0", x2="0", y2="10")
        my_subelement(defs, 'line', id="vtick", x1="0", y1="0", x2="10", y2="0")
        my_subelement(svg, 'rect', width=str(w_plus), height=str(h_plus), style="fill:white")
        text = my_subelement(svg, 'text', y="13")
        text.text = f'Date: {year:04}-{month:02}-{day:02} '
        tspan = my_subelement(text, 'tspan', dx="2em")
        tspan.text = 'Legend:'
        tspan.tail = ' '
        tspan = my_subelement(text, 'tspan', dx=".5em", style="fill:blue")
        tspan.text = u'■'
        tspan.tail = ' Temperature indoors '
        tspan = my_subelement(text, 'tspan', dx="1em", style="fill:green")
        tspan.text = u'■'
        tspan.tail = ' Dew point indoors '
        tspan = my_subelement(text, 'tspan', dx="1em", style="fill:red")
        tspan.text = u'■'
        tspan.tail = ' Temperature outdoors '
        tspan = my_subelement(text, 'tspan', dx="1em", style="fill:magenta")
        tspan.text = u'■'
        tspan.tail = ' Dew point outdoors'
        tspan = my_subelement(text, 'tspan', dx="1em", style="fill:rgb(180,180,180)")
        tspan.text = u'■'
        tspan.tail = ' Fan is on'
        text = my_subelement(svg, 'text', x=str(w_plus), y='13', style="text-anchor:end")
        text.text = u'Temperature/dew point in °C'
        text = my_subelement(svg, 'text', x="0", y=str(h + 72))
        text.text = 'Time in hours'

        g1 = my_subelement(svg, 'g', transform="translate(44,30)")

        for x1, x2 in fan_intervals:
            my_subelement(g1, 'rect', x=str(x1), y='.5', width=str(x2 - x1 + 1), height=str(h))

        g2 = my_subelement(g1, 'g', transform="translate(.5,.5)")
        g3 = my_subelement(g2, 'g', transform=f"translate(0,{h})")
        my_subelement(g3, 'line', x1="0", y1="0", x2=str(w), y2="0")

        for x in range(0, w + 1, w // 24):
            use = my_subelement(g3, 'use', x=str(x))
            use.set('{https://www.w3.org/1999/xlink}href', "#htick")

        g4 = my_subelement(g3, 'g', transform="translate(0,24)", style="text-anchor:middle")
        for i, x in enumerate(range(0, w + 1, w // 24)):
            text = my_subelement(g4, 'text', x=str(x))
            text.text = str(i % 24)

        my_subelement(g2, 'line', x1="0", y1="0", x2="0", y2=str(h))
        g9 = my_subelement(g2, 'g', transform="translate(-10,0)")
        for T in range(min_temperature, max_temperature + 1, 1):
            y = (f'{(h - (T - min_temperature) / float(max_temperature - min_temperature) * h):.2f}'
                 .rstrip('0').rstrip('.'))
            use = my_subelement(g9, 'use', y=y)
            use.set('{https://www.w3.org/1999/xlink}href', "#vtick")

        g10 = my_subelement(g9, 'g', transform="translate(-5,0)")
        g10.set('class', "ylabel")
        for T in range(min_temperature, max_temperature + 1, 1):
            y = (f'{(h - (T - min_temperature) / float(max_temperature - min_temperature) * h):.2f}'
                 .rstrip('0').rstrip('.'))
            text = my_subelement(g10, 'text', y=y)
            text.text = ('' if T >= 0 else u'−') + str(abs(T))

        g5 = my_subelement(g2, 'g', transform=f"translate({w},0)")
        my_subelement(g5, 'line', x1="0", y1="0", x2="0", y2=str(h))

        g6 = my_subelement(g5, 'g', x="0")
        for T in range(min_temperature, max_temperature + 1, 1):
            y = (f'{(h - (T - min_temperature) / float(max_temperature - min_temperature) * h):.2f}'
                 .rstrip('0').rstrip('.'))
            use = my_subelement(g6, 'use', y=y)
            use.set('{https://www.w3.org/1999/xlink}href', "#vtick")

        g7 = my_subelement(g6, 'g', transform="translate(40,0)")
        g7.set('class', "ylabel")
        for T in range(min_temperature, max_temperature + 1, 1):
            y = (f'{(h - (T - min_temperature) / float(max_temperature - min_temperature) * h):.2f}'
                 .rstrip('0').rstrip('.'))
            text = my_subelement(g7, 'text', y=y)
            text.text = ('' if T >= 0 else u'−') + str(abs(T))

        g8 = my_subelement(g2, 'g')
        g8.set('class', "thin")
        for T in range(min_temperature, max_temperature + 1):
            y = (f'{(h - (T - min_temperature) / float(max_temperature - min_temperature) * h):.2f}'
                 .rstrip('0').rstrip('.'))
            l = my_subelement(g8, 'line', x1="0", y1=y, x2=str(w), y2=y)
            if T % 5 == 0:
                l.attrib['class'] = 'thicker'

        if mark_end:
            l = 0
            for ii in reversed(range(len(data1))):
                if data1[ii, 0] == data1[ii, 0]:
                    l = ii + 1
                    break
            my_subelement(g2, 'line', style="stroke-dasharray:8; stroke:orange",
                          x1=str(l), x2=str(l),
                          y1="0", y2=str(h - .5))

        plot(my_subelement, g2, data1[:, 0], max_temperature, min_temperature, 'blue')
        plot(my_subelement, g2, data1[:, 1], max_temperature, min_temperature, 'green')
        plot(my_subelement, g2, data2[:, 0], max_temperature, min_temperature, 'red')
        plot(my_subelement, g2, data2[:, 1], max_temperature, min_temperature, 'magenta')

        my_elementtree = etree.ElementTree(svg)
        filename = f'fancontrol_{year:04}-{month:02}-{day:02}.svg'
        if upload:
            temp_dirname = tempfile.mkdtemp()
            temp_filename = 'fancontrol.svg.tmp'
            temp_filepath = os.path.join(temp_dirname, temp_filename)
            my_elementtree.write(temp_filepath, pretty_print=False)
            print('Upload')
            retval = subprocess.call(
                '/usr/bin/lftp -c "open ftp.kundencontroller.de; '
                f'cd www/data/fangraphs; put {temp_filepath}; mv {temp_filename} {filename}"', shell=True)
            print(f'Return value: {retval}')
            if retval != 0:
                raise RuntimeError('Upload failed')
        else:
            dirname = 'graphs'
            filepath = os.path.join(dirname, filename)
            my_elementtree.write(filepath, pretty_print=False)
    except:
        print('Error!')
        raise
    finally:
        if temp_dirname is not None:
            shutil.rmtree(temp_dirname)
            print('Removed temp dir')


if __name__ == "__main__":
    if len(sys.argv) != 2:
        exit()

    if sys.argv[1] == 'all':
        start_date = datetime.date(2016, 3, 16)
        end_date = today
        dt = datetime.timedelta(days=1)

        my_date = start_date
        while my_date < end_date:
            print(my_date)
            make_plot(my_date)
            my_date += dt
    else:
        offset = int(sys.argv[1])
        dt = datetime.timedelta(days=offset)
        make_plot(today - dt, upload=True, mark_end=(offset == 0))
