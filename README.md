# pySOCKS5-iOS #
PiHole and a SOCKS5 proxy server rolled into one convenient script!

100% guaranteed to bypass carrier throttling of client devices connected to an iPhone hotspot. It uses asyncio for high performance and includes a built-in DNS Sinkhole (Pi-hole) to save cellular bandwidth.

## Features ##
* **Zero Dependencies:** Runs on standard Python 3 in Pythonista (no `pip install` needed).
* **Ad-Blocking:** Automatically downloads the StevenBlack Unified Hosts list (~100k domains) to block ads/trackers *before* they use your data.
* **TCP Optimization:** Tuned for iOS memory constraints (Jetsam) by rejecting unstable UDP/QUIC streams.
* **Instant Restart:** Uses `SO_REUSEADDR` to prevent socket locking when restarting scripts.

## Usage (iOS) ##
1.  OpenPythonista 3.
2.  Drop `pySOCKS5.py` (and/or `debug_pySOCKS5.py' if you want to diagnose a connection issue`) into your script folder.
3.  Activate your iPhone's personal hotspot.
4.  Make a note of the IPv4 and IPv6 addresses (Windows will list them under Gateway Address) your client device sees when it connects to your hotspot
5.  Run the script. 

> **Note:** To kill the script, simply press the "X" button in Pythonista. The script is designed to catch the kill signal and release the port immediately.

---

## Windows Client Configuration ##
For the best experience, do not use the native Windows Proxy settings. Use one of the following tools:

### Option 1: Proxifier (Recommended) ###
This offers the most granular control, allowing you to route specific apps while blocking telemetry.
* **Server Address:** `172.20.10.1` (or whatever your iphone's IP address is)
* **Port:** `9999`
* **Protocol:** SOCKS Version 5
* **Recommended Rule Order:**
    1.  **Any Application** (%ComputerName%; 127.0.0.1 - 127.255.255.255; ::1; localhost; fd00:: - fdff:ffff:ffff:ffff:ffff:ffff:ffff:ffff) -> **Action: Direct** (Crucial for system stability).
    2.  **Any Application** ([iPhone IPv6 address]; [iPhone IPv4 address`) -> **Action: Direct** (Allows DNS resolution).
    3.  **Any Application** (Microsoft/Ad domains) -> **Action: Block** (Saves data).
    4.  **Work Apps** (Edge, Update) -> **Action: Proxy**.
    5.  **Default Apps** -> **Action: Direct** (Prevents leaks).

### Option 2: Tun2Socks + WinTun ###
If you prefer a free, open-source "VPN-like" experience that forces *everything* through the tunnel.
* **Tool:** [Tun2Socks](https://github.com/xjasonlyu/tun2socks)
* **Interface:** Uses the high-performance WireGuard `wintun` driver.
* **Command:**
  ```powershell
  path\to\tun2socks.exe -proxy socks5://[iphone_IPv4]:9999 -device wintun -interface "[Your adapter's exact name]" -udp-timeout 1m
  ```
  For example -
  ```powershell
  .\tun2socks.exe -proxy socks5://172.20.10.1:9876 -device wintun -interface "Wi-Fi" -udp-timeout 1m
  ```
* *Pros:* Catches everything, no leak configuration needed.
* *Cons:* Harder to filter out junk telemetry traffic.

### Option 3: SSTap (Gaming/UDP) ##
If you are attempting to game or use applications that require heavy UDP usage.
* **Note:** pySOCKS5 is TCP-only (to prevent iOS crashes). SSTap can "fake" a TCP wrapper for some UDP games, but performance may vary.

## Mac/Android/Etc. ##
[to do]

---

## Limitations ##
1.  **No UDP Support:** The script actively rejects UDP association requests (`CMD 0x03`). This is intentional.
    * **Fix:** Disable "Experimental QUIC Protocol" in Edge/Chrome flags (`edge://flags`) to force browsers to use TCP.
2.  **iOS Backgrounding:** If you minimize Pythonista, iOS may pause the script after 30 seconds unless you use a "keep-alive" trick (good luck finding one that works). You must run this script on the foreground.
3.  **IPv6:** While the script handles IPv6 tunneling, cellular carriers often have unstable IPv6 routing for tethered data. If you see "Host Unreachable," force your client to use IPv4.

## Debugging
Use `debug_pySOCKS5.py` if you are experiencing connection drops. It writes a verbose log to `pysocks5_debug.log` in the same directory, detailing every handshake and byte transfer.
