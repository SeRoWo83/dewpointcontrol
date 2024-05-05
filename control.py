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

import os
import time
import logging
import logging.handlers
from configparser import RawConfigParser

from component import allThreadsAlive
from uptime import uptime, uptime_as_string
from messageboard import message_board
from signalshandler import SignalsHandler
from average import Average
from dcf77_thread import DCF77
from devices import Devices
from display import Display
from htmlwriter import HtmlWriter
from menu import Menu
from fan import Fan
from sensor import Sensor
from status import Status
from wlan import RestartWLAN, CheckNetwork


def main() -> None:
    config = RawConfigParser()  # TODO: Use tomllib
    config.read('fancontrol.cfg')
    logfile = config.get('logging', 'logfile')

    logdir = os.path.dirname(os.path.abspath(logfile))
    if not os.path.isdir(logdir):
        os.makedirs(logdir)

    logger = logging.getLogger('fancontrol')
    logger.setLevel(logging.INFO)

    class ContextFilter(logging.Filter):
        def filter(self, record) -> bool:
            record.uptime = uptime_as_string()
            return True

    logger.addFilter(ContextFilter())
    # File handler: rotate logs daily, keep logs > 2 years
    fh = logging.handlers.TimedRotatingFileHandler(logfile, when='midnight', backupCount=750)

    class UTCFormatter(logging.Formatter):
        converter = time.gmtime

    fh.setFormatter(UTCFormatter('%(asctime)s,%(uptime)s,%(levelno)s,%(filename)s,%(message)s'))
    logger.addHandler(fh)
    # Console handler: for warnings and errors
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter('%(asctime)s: %(levelname)s: %(message)s'))
    logger.addHandler(ch)

    logger.info('Startup')

    signals_handler = SignalsHandler(message_board)

    with (
        Display(),
        Sensor(),
        Status(),
        HtmlWriter(),
        Fan(),
        Menu(),
        Devices(),
        DCF77(),
        Average(),
        RestartWLAN(),
        CheckNetwork(),
    ):
        logger.info('Start')
        time0: float = uptime()
        while message_board.query('ExitThread') is None:
            exception = message_board.query('Exception')
            if exception is not None:
                raise exception
            message_board.post('Time', (uptime(), time.localtime()))
            time1 = uptime()
            if time1 < time0:
                logger.warning(f'Error in uptime: {time1} < {time0}.')
                time0 = time1
            sleep_time = 1 - time1 + time0
            if sleep_time <= 0:
                logger.warning(f'Zero sleep time: {time0} < {time1}, Δ={time1 - time0:.1f}s.')
            while sleep_time > 0:
                time.sleep(sleep_time)
                time1 = uptime()
                sleep_time = 1 - time1 + time0
            if sleep_time > -.1:
                time0 += 1
            else:
                logger.warning(f'Sleep longer than expected: {time0} < {time1}, Δ={time1 - time0:.1f}s.')
                time0 = time1
            if not allThreadsAlive():
                message_board.post('ExitThread', True)

    logger.info('Shutdown')


if __name__ == '__main__':
    main()
