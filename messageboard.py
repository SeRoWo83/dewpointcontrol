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

from typing import Callable
from weakref import ref
from collections import OrderedDict

from rwlock import RWLock, RWLockReaderPriority


class MessageBoard:
    def __init__(self):
        self.messages: dict[str, ...] = {}
        self.message_lock: RWLock = RWLock()
        self.subscriptions: dict[str, ...] = {}
        self.subscription_lock: RWLockReaderPriority = RWLockReaderPriority()

    def post(self, heading: str, message) -> None:
        with self.message_lock.write_access:
            self.messages[heading] = message
        with self.subscription_lock.read_access:
            if heading in self.subscriptions:
                for wr, callback in self.subscriptions[heading].items():
                    instance = wr()
                    if instance is not None:
                        callback(instance, message)

    def query(self, heading: str) -> ...:
        with self.message_lock.read_access:
            if heading in self.messages:
                return self.messages[heading]

    def subscribe(self, heading: str, instance: object, callback: Callable) -> None:
        with self.subscription_lock.write_access:
            if heading not in self.subscriptions:
                self.subscriptions[heading] = OrderedDict()
            wr = ref(instance)
            assert wr not in self.subscriptions[heading]
            self.subscriptions[heading][wr] = callback

    def unsubscribe(self, heading: str, instance: object) -> None:
        with self.subscription_lock.write_access:
            wr = ref(instance)
            if heading in self.subscriptions and wr in self.subscriptions[heading]:
                del self.subscriptions[heading][wr]
            if not self.subscriptions[heading]:
                del self.subscriptions[heading]

    def unsubscribe_all(self, instance: object) -> None:
        with self.subscription_lock.write_access:
            wr = ref(instance)
            for heading in list(self.subscriptions):
                if wr in self.subscriptions[heading]:
                    del self.subscriptions[heading][wr]
                if not self.subscriptions[heading]:
                    del self.subscriptions[heading]

    def ask(self, heading: str, message) -> ...:
        with self.subscription_lock.read_access:
            if heading in self.subscriptions:
                for wr, callback in self.subscriptions[heading].items():
                    instance = wr()
                    if instance is not None:
                        return callback(instance, message)


message_board = MessageBoard()
