#!/usr/bin/env python
# -*- coding: utf-8 -*-

from time import sleep

from uptime import uptime


class CSV:
    def __init__(self, *args):
        self.args = args

    def __str__(self):
        return ','.join(map(str, self.args))


def delay(seconds):
    time0 = uptime()
    sleep_time = seconds
    while sleep_time > 0:
        sleep(sleep_time)
        time1 = uptime()
        sleep_time = seconds + time0 - time1
