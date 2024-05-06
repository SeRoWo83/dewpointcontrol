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

from threading import Lock, Thread
import logging
from typing import Self

from messageboard import message_board as my_message_board, MessageBoard
from shutdown import shutdown

logger = logging.getLogger('fancontrol')


class Component:
    message_board = my_message_board

    def __init__(self, name: str) -> None:
        self.name = name
        self.lock = Lock()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.message_board.unsubscribe_all(self)
        self.message_board.post('ExitThread', True)
        print(f'Exit {self.name} worker.')


class ComponentWithThread(Component):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.thread = Thread(target=self.__run, name=self.name)

    def __enter__(self) -> Self:
        self.thread.start()
        threadManager.add_thread(self)
        return super().__enter__()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        super().__exit__(exc_type, exc_value, traceback)
        self.stop()

    def __run(self) -> None:
        try:
            self.run()
        except:
            raise
        finally:
            print(f'Leave {self.name} thread.')

    def run(self) -> None:
        # This method should be overridden by child classes similar to built in threads
        pass

    def stop(self) -> None:
        print(f'Join {self.name} thread.')
        self.thread.join()
        print(f'The {self.name} thread has joined.')

    def is_alive(self) -> bool:
        return self.thread.is_alive()


class ThreadManager:
    def __init__(self, message_board: MessageBoard) -> None:
        self.worker_threads: list[ComponentWithThread] = []
        self.message_board = message_board
        self.message_board.subscribe('Shutdown', self, ThreadManager.on_shutdown)

    def add_thread(self, thread: ComponentWithThread) -> None:
        self.worker_threads.append(thread)

    def all_threads_alive(self) -> bool:
        for thread in self.worker_threads:
            if not thread.is_alive():
                logger.error(f'The {thread.name} thread died.')
                return False
        return True

    def on_shutdown(self, _) -> None:
        logger.info('Shutdown by user request')
        my_message_board.post('ExitThread', True)
        for thread in self.worker_threads:
            thread.stop()
        print('System shutdown')
        shutdown()


threadManager = ThreadManager(my_message_board)

allThreadsAlive = threadManager.all_threads_alive
