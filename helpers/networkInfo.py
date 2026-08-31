"""
The MIT License (MIT)

Copyright (c) 2026 Hoshino Yuki

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""    

# SPDX-License-Identifier: MIT

import ifaddr
import ipaddress
import sys
import subprocess


class NetworkInfo:
    """
    Cross-platform local network interface info.

    Addresses/subnets via ifaddr (works everywhere).
    
    Gateways are OS-specific and dispatched by platform; they return None if the
    lookup fails or the platform is unsupported, never raising.
    """

    def __init__(self, skip_loopback: bool = True, ipv6_global_only: bool = False):
        self._skip_loopback = skip_loopback
        self._ipv6_global_only = ipv6_global_only

        self.ipv4_addresses: list[str] = []
        self.ipv4_subnets: list[str] = []
        self.ipv6_addresses: list[str] = []

        self._collectInterfaces()

        self.ipv4_gateway = self._getDefaultGatewayV4()
        self.ipv6_gateway = self._getDefaultGatewayV6()


    def _collectInterfaces(self) -> None:
        for adapter in ifaddr.get_adapters():
            for ip in adapter.ips:
                if ip.is_IPv4:
                    if self._skip_loopback and ip.ip == "127.0.0.1":
                        continue

                    self.ipv4_addresses.append(ip.ip)
                    netmask = str(ipaddress.IPv4Network(f"0.0.0.0/{ip.network_prefix}").netmask)
                    self.ipv4_subnets.append(netmask)

                elif ip.is_IPv6:
                    addr = ip.ip[0]
                    if self._skip_loopback and addr == "::1":
                        continue

                    if self._ipv6_global_only and not ipaddress.ip_address(addr).is_global:
                        continue

                    self.ipv6_addresses.append(f"{addr}/{ip.network_prefix}")


    # ---- Gateway dispatch ----

    def _getDefaultGatewayV4(self) -> str | None:
        try:
            if sys.platform.startswith("linux"):
                return self._gwV4_linux()

            elif sys.platform == "win32":
                return self._gwV4_windows()

            elif sys.platform == "darwin":
                return self._gwV4_bsd()

        except Exception:
            return

        return


    def _getDefaultGatewayV6(self) -> str | None:
        try:

            if sys.platform.startswith("linux"):
                return self._gwV6_linux()

            elif sys.platform == "win32":
                return self._gwV6_windows()

            elif sys.platform == "darwin":
                return self._gwV6_bsd()

        except Exception:
            return

        return


    # ---- Linux (/proc) ----

    def _gwV4_linux(self) -> str | None:
        with open("/proc/net/route") as f:
            for line in f.readlines()[1:]:
                fields = line.strip().split()
                if fields[1] == "00000000" and int(fields[3], 16) & 2:
                    gw_hex = fields[2]
                    return ".".join(str(int(gw_hex[i:i+2], 16)) for i in (6, 4, 2, 0))

        return

    def _gwV6_linux(self) -> str | None:
        with open("/proc/net/ipv6_route") as f:
            for line in f.readlines():
                fields = line.strip().split()
                if fields[0] == "0" * 32 and fields[1] == "00":
                    gw_raw = fields[4]
                    if gw_raw == "0" * 32:
                        continue

                    gw = ":".join(gw_raw[i:i+4] for i in range(0, 32, 4))
                    return str(ipaddress.IPv6Address(gw))

        return


    # ---- macOS / BSD (netstat) ----

    def _gwV4_bsd(self) -> str | None:
        out = subprocess.run(["netstat", "-rn", "-f", "inet"],
                            capture_output=True, text=True, timeout=5).stdout
        for line in out.splitlines():
            fields = line.split()
            if fields and fields[0] == "default":
                return fields[1]

        return

    def _gwV6_bsd(self) -> str | None:
        out = subprocess.run(["netstat", "-rn", "-f", "inet6"],
                            capture_output=True, text=True, timeout=5).stdout
        for line in out.splitlines():
            fields = line.split()
            if fields and fields[0] == "default" and ":" in fields[1]:
                return fields[1].split("%")[0]   # strip scope id

        return


    # ---- Windows (Win32 API via ctypes) ----

    def _gwV4_windows(self) -> str | None:
        return self._gw_windows(family=2)    # AF_INET

    def _gwV6_windows(self) -> str | None:
        return self._gw_windows(family=23)   # AF_INET6

    def _gw_windows(self, family: int) -> str | None:
        """
        Query the best-route gateway via the IP Helper API (GetBestRoute
        isn't ideal for this.
        
        We parse `route print` instead, which is
        locale-independent for the 0.0.0.0 / :: default rows).

        Parameters
        ----------
        family : int
            Address family (2 for IPv4, 23 for IPv6).

        Returns
        -------
        str | None
            The default gateway address, or None if not found.
        """

        try:
            out = subprocess.run(["route", "print"],
                                capture_output=True, text=True, timeout=5).stdout
        except Exception:
            return

        if family == 2:      # IPv4: look for the 0.0.0.0 default row
            for line in out.splitlines():
                fields = line.split()
                if len(fields) >= 3 and fields[0] == "0.0.0.0" and fields[1] == "0.0.0.0":
                    return fields[2]   # gateway column
        else:                # IPv6: look for the ::/0 default row
            for line in out.splitlines():
                fields = line.split()
                if "::/0" in fields:
                    # gateway is typically the last field on the row
                    for f in reversed(fields):
                        if ":" in f and f != "::/0":
                            return f.split("%")[0]

        return
