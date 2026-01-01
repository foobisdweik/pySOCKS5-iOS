import asyncio
import socket
import struct
import sys
import urllib.request
import re

# --- CONFIGURATION ---
# 1. THE "SAFE" LIST (Immediate Protection)
# These specific domains are blocked instantly. 
BLOCKLIST = {
    # Microsoft Telemetry
    "vortex.data.microsoft.com",
    "settings-win.data.microsoft.com",
    "telemetry.microsoft.com",
    "browser.events.data.msn.com",
    # Google Ads/Tracking (BUT NOT GMAIL/YOUTUBE)
    "doubleclick.net",
    "googleadservices.com",
    "adservice.google.com",
    "googletagservices.com",
    "analytics.google.com",
    "pagead2.googlesyndication.com",
    # Social/Other
    "scorecardresearch.com",
    "quantserve.com",
    "facebook.com", # Optional: Remove if you use FB
    "connect.facebook.net",
    "pixel.facebook.com"
}

# 2. REMOTE BLOCKLIST (The "Real" Pi-hole)
# Set True to download a 2MB+ list of ad domains on startup.
USE_REMOTE_BLOCKLIST = True
REMOTE_LIST_URL = "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts"

async def update_blocklist():
    """Downloads and parses a standard hosts file in the background."""
    if not USE_REMOTE_BLOCKLIST:
        return
    
    print("[*] Background: Downloading massive ad-block list...")
    try:
        # Run blocking I/O in a separate thread so the proxy doesn't freeze
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, lambda: urllib.request.urlopen(REMOTE_LIST_URL).read().decode('utf-8'))
        
        count = 0
        # Regex to find lines like "0.0.0.0 ad.doubleclick.net"
        # We skip lines that are comments (#) or localhost
        for line in data.splitlines():
            if line.startswith("0.0.0.0") and not line.startswith("0.0.0.0 0.0.0.0"):
                parts = line.split()
                if len(parts) >= 2:
                    domain = parts[1]
                    if domain != "0.0.0.0":
                        BLOCKLIST.add(domain)
                        count += 1
        
        print(f"[+] Update Complete: {count} ad domains added to sinkhole.")
    except Exception as e:
        print(f"[!] Blocklist Update Failed: {e}")

def is_blocked(domain):
    """Checks if a domain is in the blocklist."""
    domain = domain.lower()
    if domain in BLOCKLIST:
        return True
    
    # Check for subdomains of blocked parents (e.g. 'ads.doubleclick.net' matches 'doubleclick.net')
    # For speed, we rely on the massive list having exact matches usually.
    parts = domain.split('.')
    if len(parts) > 2:
        parent = ".".join(parts[-2:]) # Check 'google.com'
        if parent in BLOCKLIST:
            return True
    return False

class SOCKS5Server:
    def __init__(self, host='0.0.0.0', port=9999):
        self.host = host
        self.port = port

    async def handle_client(self, reader, writer):
        try:
            # Step 1: Greeting
            header = await reader.read(2)
            if not header: return
            version, nmethods = struct.unpack("!BB", header)
            await reader.read(nmethods)
            writer.write(struct.pack("!BB", 5, 0)) 
            await writer.drain()

            # Step 2: Request
            request = await reader.read(4)
            if not request: return
            version, cmd, _, address_type = struct.unpack("!BBBB", request)

            if cmd != 1: # Only CONNECT
                writer.write(struct.pack("!BBBBIH", 5, 7, 0, 1, 0, 0))
                await writer.drain(); writer.close(); return

            dest_address = ""
            if address_type == 1: # IPv4
                dest_address = socket.inet_ntoa(await reader.read(4))
            elif address_type == 3: # Domain
                domain_length = ord(await reader.read(1))
                dest_address = (await reader.read(domain_length)).decode()
            elif address_type == 4: # IPv6
                dest_address = socket.inet_ntop(socket.AF_INET6, await reader.read(16))
            else:
                writer.close(); return
            
            dest_port = struct.unpack("!H", await reader.read(2))[0]

            # --- SINKHOLE LOGIC ---
            if address_type == 3 and is_blocked(dest_address):
                # print(f"[BLOCKED] {dest_address}") # Uncomment to see what dies
                writer.write(struct.pack("!BBBBIH", 5, 2, 0, 1, 0, 0)) # 0x02 = Ruleset Deny
                await writer.drain(); writer.close(); return
            # ----------------------

            # Step 3: Tunnel
            try:
                remote_reader, remote_writer = await asyncio.wait_for(
                    asyncio.open_connection(dest_address, dest_port), timeout=10
                )
                writer.write(struct.pack("!BBBBIH", 5, 0, 0, 1, 0, 0))
                await writer.drain()
            except:
                writer.write(struct.pack("!BBBBIH", 5, 4, 0, 1, 0, 0))
                await writer.drain(); writer.close(); return

            # Step 4: Data Relay
            async def relay(src, dst):
                try:
                    while True:
                        data = await src.read(16384) # High-speed buffer
                        if not data: break
                        dst.write(data)
                        await dst.drain()
                except: pass
                finally: 
                    try: dst.close(); await dst.wait_closed()
                    except: pass

            await asyncio.gather(relay(reader, remote_writer), relay(remote_reader, writer), return_exceptions=True)

        except: pass
        finally:
            writer.close()
            try: await writer.wait_closed()
            except: pass

    async def run(self):
        # Start the background updater
        asyncio.create_task(update_blocklist())
        
        server = await asyncio.start_server(self.handle_client, self.host, self.port, reuse_address=True)
        print(f"[*] Pi-hole SOCKS5 Active on {self.host}:{self.port}")
        
        async with server:
            try: await server.serve_forever()
            except asyncio.CancelledError: pass
            finally: server.close(); await server.wait_closed()

if __name__ == '__main__':
    try: asyncio.run(SOCKS5Server().run())
    except KeyboardInterrupt: sys.exit(0)