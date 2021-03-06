# Author: echel0n <echel0n@sickrage.ca>
# URL: https://sickrage.ca
#
# This file is part of SickRage.
#
# SickRage is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickRage is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickRage.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function, unicode_literals, with_statement

import socket

from .upnp import Device
from .util import _getLogger


def interface_addresses(family=socket.AF_INET):
    try:
        for fam, __, __, __, sockaddr in socket.getaddrinfo('', None):
            if family == fam:
                yield sockaddr[0]
    except socket.gaierror:
        pass


def scan(timeout=5):
    """
    Discover UPnP devices on the network via UDP multicast. Returns a list
    of dictionaries, each of which contains the HTTPMU reply headers.
    """

    ssdp_replies = []
    servers = []

    msg = \
        'M-SEARCH * HTTP/1.1\r\n' \
        'HOST:239.255.255.250:1900\r\n' \
        'MAN:"ssdp:discover"\r\n' \
        'MX:2\r\n' \
        'ST:upnp:rootdevice\r\n' \
        '\r\n'

    # Send discovery broadcast message
    for addr in interface_addresses():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.settimeout(timeout)
        s.bind((addr, 0))
        s.sendto(msg, ('239.255.255.250', 1900))

        try:
            while True:
                data, addr = s.recvfrom(65507)
                ssdp_reply_headers = {}
                for line in data.splitlines():
                    if ':' in line:
                        key, value = line.split(':', 1)
                        ssdp_reply_headers[key.strip().lower()] = value.strip()
                if not ssdp_reply_headers in ssdp_replies:
                    # Prevent multiple responses from showing up multiple
                    # times.
                    ssdp_replies.append(ssdp_reply_headers)
        except socket.timeout:
            pass

        s.close()

    return (ssdp_replies)


def discover(timeout=5):
    """
    Convenience method to discover UPnP devices on the network. Returns a
    list of `upnp.Device` instances. Any invalid servers are silently
    ignored.
    """
    devices = {}
    for entry in scan(timeout):
        if entry['location'] in devices:
            continue
        try:
            devices[entry['location']] = Device(entry['location'])
        except Exception as exc:
            log = _getLogger("ssdp")
            log.error('Error \'%s\' for %s', exc, entry['location'])
    return list(devices.values())
