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

from typing import Any, Self
from sht75 import SensorData
from component import Component

C_ERROR: tuple[int, int, int] = (255, 0, 0)
C_OK: tuple[int, int, int] = (0, 127, 0)
C_ALERT: tuple[int, int, int] = (0, 159, 255)
C_MEASURE: tuple[int, int, int] = (0, 159, 255)

C_HTML_ERROR = 'color:red'
C_HTML_OK = 'color:#007f00'
C_HTML_ALERT = 'color:#009fff'


class Status(Component):
    def __init__(self) -> None:
        super().__init__('status')
        self.new_measurement: bool = False
        self.measurement_error: bool = False
        self.ip_address = None
        self.last_html_status = None

    def __enter__(self) -> Self:
        with self.lock:
            self.message_board.subscribe('Measurement', self, Status.on_measurement)
            self.message_board.subscribe('StatusProcessed', self, Status.on_status_processed)
            self.message_board.subscribe('Mode', self, Status.on_mode)
        return super().__enter__()

    def on_measurement(self, message: tuple[float, SensorData, SensorData]):
        with self.lock:
            self.new_measurement = True
            _, s1_data, s2_data = message
            self.measurement_error = s1_data.error or s2_data.error

            self.__generate_display_status()
            self.__generate_html_status()

    def on_status_processed(self, _: Any) -> None:  # TODO: Input required? For callback usage?
        with self.lock:
            if self.new_measurement:
                self.new_measurement = False
                self.__generate_display_status()

    def on_mode(self, _: Any) -> None:  # TODO: Input required? For callback usage?
        with self.lock:
            self.__generate_display_status()

    def __generate_html_status(self) -> None:
        last_sync = self.message_board.query('DCF77TimeSync')
        if self.measurement_error:
            status = ('Sensor error.', C_HTML_ERROR, last_sync)
        elif last_sync is None:
            status = ('Wait for radio clock signal.', C_HTML_ALERT, last_sync)
        else:
            fan_comment = self.message_board.query('FanComment')
            if fan_comment is None:
                fan_comment = 'N/A'
            error = 'error' in fan_comment or 'Error' in fan_comment
            color = C_HTML_ERROR if error else C_HTML_OK
            status_txt = 'Error' if error else 'OK'
            status = (f'Status: {status_txt}. {fan_comment}', color, last_sync)
        if status != self.last_html_status:
            self.last_html_status = status
            self.message_board.post('HTMLStatus', status)

    def __generate_display_status(self) -> None:
        if self.new_measurement:
            status = ('Messung.', C_MEASURE)
        elif self.measurement_error:
            status = ('Sensorfehler.', C_ERROR)
        elif self.message_board.query('DCF77TimeSync') is None:
            status = ('Warte auf Funksignal.', C_ALERT)
        else:
            mode = self.message_board.query('Mode')
            if mode == 'manual':
                status = ('Status: OK (manuell).', C_OK)
            else:
                status = ('Status: OK (Automatik).', C_OK)
        self.message_board.post('Status', status)
