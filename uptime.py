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

from typing import TextIO
from threading import Lock
from time import clock_gettime, CLOCK_BOOTTIME


class _Uptimefile:
    def __init__(self):
        self.f: TextIO = open("/proc/uptime", 'r').__enter__()

    def __del__(self):
        print('Close file /proc/uptime.')
        self.f.__exit__()

    def file(self):
        return self.f


_uptime_file: _Uptimefile = _Uptimefile()
_f: TextIO = _uptime_file.file()
_lock: Lock = Lock()


def uptime_as_string_old():
    # Uptime in Seconds
    with _lock:
        _f.seek(0)
        return _f.read().split()[0]


def uptime_old():
    # Uptime in Seconds
    return float(uptime_as_string_old())


def uptime() -> float:
    # Uptime in Seconds
    return round(clock_gettime(CLOCK_BOOTTIME), 3)  # TODO: maybe keep precision


def uptime_as_string() -> str:
    return f"{uptime():.3f}"


if __name__ == '__main__':
    from timeit import default_timer as timer
    print(f"{uptime_as_string_old()=}")
    print(f"{uptime_as_string()    =}")  # noqa
    start: float = timer()
    print(f"{uptime_old()=}")
    mid: float = timer()
    print(f"{uptime()    =}")  # noqa
    end: float = timer()
    print(f"uptime_old() duration: {mid-start:.8f}s")
    print(f"uptime() duration:     {end-mid:.8f}s")
