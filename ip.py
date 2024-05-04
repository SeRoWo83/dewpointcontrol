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

from fcntl import ioctl
from socket import socket, AF_INET, SOCK_DGRAM, inet_ntoa
from struct import pack
from requests import Response, get as url_get


def get_ip_address(if_name: str = 'wlan0') -> str:
    # Source: https://code.activestate.com/recipes/439094/
    try:
        with socket(AF_INET, SOCK_DGRAM) as s:
            return inet_ntoa(ioctl(s.fileno(), 0x8915,  # SIOCGIFADDR
                                   pack('256s', if_name[:15].encode('utf-8')))[20:24])
    except IOError:
        return 'None'


def get_wan_ip() -> str:
    try:
        r: Response = url_get('https://whatismyip.akamai.com', timeout=1, stream=True)
        # Validate the result: a plain text ip address.
        ip = r.raw.read(15).decode()
        for c in ip:
            if c not in '0123456789.':
                return 'Error'
        return ip
    except:
        return 'Error'


if __name__ == '__main__':
    print(get_ip_address())
    print(get_wan_ip())
