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
import os
import time
from datetime import datetime

from component import ComponentWithThread
from dcf77_reader import Receiver

logger = logging.getLogger('fancontrol')


class DCF77(ComponentWithThread):
    def __init__(self) -> None:
        super().__init__('DCF77 receiver')

    def __callback(self, dcf77_time: datetime) -> None:
        # Format date/time string
        utctime = dcf77_time.utctimetuple()
        time_date_str = time.strftime("\"%Y-%m-%d %H:%M:00\"", utctime)
        # Set system time
        retval = os.system(f"date -u -s {time_date_str} > /dev/null")
        if retval != 0:
            logger.error(f'"date" command return value is {retval}.')
        time_date_str = (f"{dcf77_time.day:02d}.{dcf77_time.month:02d}.{dcf77_time.year:4d}, "
                         f"{dcf77_time.hour:02d}:{dcf77_time.minute:02d} {dcf77_time.tzinfo.tzname(dcf77_time)}")
        self.message_board.post('DCF77TimeSync', time_date_str)
        logger.info(f'dcf77,{time_date_str}')

    def run(self) -> None:
        def break_event() -> bool:
            return self.message_board.query('ExitThread') is not None

        r = Receiver(callback=self.__callback, break_event=break_event)
        r.run()
