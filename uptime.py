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

from time import clock_gettime, CLOCK_BOOTTIME


def uptime() -> float:
    # Uptime in Seconds
    return clock_gettime(CLOCK_BOOTTIME)


def uptime_as_string() -> str:
    return f"{uptime():.3f}"


if __name__ == '__main__':
    from timeit import default_timer as timer
    print(f"{uptime_as_string()=}")
    start: float = timer()
    print(f"{uptime()=}")
    end: float = timer()
    print(f"uptime() duration: {end-start:.8f}s")
