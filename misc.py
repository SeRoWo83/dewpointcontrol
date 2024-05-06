#!/usr/bin/env python
# -*- coding: utf-8 -*-

from time import sleep
from numpy import NaN
from dataclasses import dataclass

from uptime import uptime


@dataclass
class SensorData:
    humidity: float = NaN
    temperature: float = NaN
    dewpoint: float = NaN
    error: bool = False


class CSV:
    def __init__(self, *args) -> None:
        self.args = args

    def __str__(self) -> str:
        return ','.join(map(str, self.args))


def delay(seconds: float) -> None:
    time0 = uptime()
    sleep_time = seconds
    while sleep_time > 0:
        sleep(sleep_time)
        time1 = uptime()
        sleep_time = seconds + time0 - time1


if __name__ == '__main__':
    print(CSV('test', delay(3)))
