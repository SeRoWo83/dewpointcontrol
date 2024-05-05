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
import signal
import sys
from threading import current_thread
from types import FrameType
from typing import Any, Callable

from messageboard import MessageBoard

logger = logging.getLogger('fancontrol')


class SignalsHandler:
    def __init__(self, message_board: MessageBoard) -> None:
        self.message_board = message_board
        signal.signal(signal.SIGINT, self.generate_sigint_handler())
        signal.signal(signal.SIGTERM, self.generate_sigterm_handler())
        signal.signal(signal.SIGUSR1, self.generate_sigusr1_handler())
        signal.signal(signal.SIGUSR2, self.generate_sigusr2_handler())
        signal.signal(signal.SIGHUP, self.generate_sighup_handler())

    def generate_sigint_handler(self) -> Callable[[int, FrameType | None], Any]:
        def sigint_handler(_signal: int, _frame: FrameType) -> None:
            print(f'Process {os.getpid()}, thread {current_thread().name}: SIGINT received.')
            self.message_board.post('ExitThread', True)
            logger.info('SIGINT received: exit.')
            sys.exit()
        return sigint_handler

    def generate_sigterm_handler(self) -> Callable:
        def sigterm_handler(_signal: int, _frame: FrameType) -> None:
            print(f'Process {os.getpid()}, thread {current_thread().name}: SIGTERM received.')
            self.message_board.post('ExitThread', True)
            logger.info('SIGTERM received: exit.')
            sys.exit()
        return sigterm_handler

    @staticmethod
    def generate_sigusr1_handler() -> Callable:
        def sigusr1_handler(_signal: int, _frame: FrameType) -> None:
            print(f'Process {os.getpid()}, thread {current_thread().name}: SIGUSR1 received.')
            logger.info('SIGUSR1 received: ignore.')
        return sigusr1_handler

    @staticmethod
    def generate_sigusr2_handler() -> Callable:
        def sigusr2_handler(_signal: int, _frame: FrameType) -> None:
            print(f'Process {os.getpid()}, thread {current_thread().name}: SIGUSR2 received.')
            logger.info('SIGUSR2 received: ignore.')
        return sigusr2_handler

    @staticmethod
    def generate_sighup_handler() -> Callable:
        def sighup_handler(_signal: int, _frame: FrameType) -> None:
            print(f'Process {os.getpid()}, thread {current_thread().name}: SIGHUP received.')
            logger.info('SIGHUP received: ignore.')
        return sighup_handler
