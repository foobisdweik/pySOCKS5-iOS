import asyncio
import socket
import struct
import sys
import urllib.request
import logging

# --- LOGGING CONFIGURATION ---
# Console: Clean, high-level info only.
# File: Absolute chaos (Debug level).
logger = logging.getLogger("pySOCKS5")
logger.setLevel(logging.DEBUG)

# File Handler (Log with a shit ton of output)
file_handler = logging.FileHandler("pysocks5_debug.log", mode='w')
file_handler.setLevel(logging.DEBUG)
file_fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_fmt)

# Console Handler (Sane console output)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_fmt = logging.Formatter('%(message)s')
console_handler.setFormatter(console_fmt)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# --- CONFIGURATION ---
BLOCKLIST = {
    "vortex.data.microsoft.com",
    "settings-win.data.microsoft.com",
    "telemetry.microsoft.com",
    "browser.events.data.msn.com",
    "doubleclick.net",
    "googleadservices.com",
    "adservice.google.com",
    "googletagservices.com",
    "analytics.google.com",
    "pagead2.googlesyndication.com",
    "scorecardresearch.com",
    "quantserve.com"
}

USE_REMOTE_BLOCKLIST = True
REMOTE_LIST_URL = "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts"

async def update_blocklist():
    if not USE_REMOTE_BLOCKLIST: return
    
    logger.info("[*] Background: Downloading massive ad-block list...")
    logger.debug(f"Fetching from {REMOTE_LIST_URL}")
    
    try:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, lambda: urllib.request.urlopen(REMOTE_LIST_URL).read().decode('utf-8'))
        
        count = 0
        for line in data.splitlines():
            if line.startswith("0.0.0.0") and not line.startswith("0.0.0.0 0.0.0.0"):
                parts = line.split()
                if len(parts) >= 2:
                    domain = parts[1]
                    if domain != "0.0.0.0":
                        BLOCKLIST.add(domain)
                        count += 1
        
        logger.info(f"[+] Update Complete: {count} ad domains added to sinkhole.")
    except Exception as e:
        logger.error(f"[!] Blocklist Update Failed: {e}")

def is_blocked(domain):
    domain = domain.lower()
    if domain in BLOCKLIST:
        return True
    parts = domain.split('.')
    if len(parts) > 2:
        parent = ".".join(parts[-2:])
        if parent in BLOCKLIST:
            return True
    return False

class SOCKS5Server:
    def __init__(self, host='0.0.0.0', port=9999):
        self.host = host
        self.port = port

    async def handle_client(self, reader, writer):
        peer = writer.get_extra_info('peername')
        client_id = f"{peer[0]}:{peer[1]}"
        logger.debug(f"[{client_id}] New connection opened.")

        try:
            # Step 1: Greeting
            header = await reader.read(2)
            if not header: return
            version, nmethods = struct.unpack("!BB", header)
            methods = await reader.read(nmethods)
            
            logger.debug(f"[{client_id}] VER={version} METHODS={methods}")
            
            writer.write(struct.pack("!BB", 5, 0)) 
            await writer.drain()

            # Step 2: Request
            request = await reader.read(4)
            if not request: return
            version, cmd, _, address_type = struct.unpack("!BBBB", request)

            if cmd != 1: 
                logger.debug(f"[{client_id}] Unsupported CMD: {cmd}")
                writer.write(struct.pack("!BBBBIH", 5, 7, 0, 1, 0, 0))
                await writer.drain(); writer.close(); return

            dest_address = ""
            if address_type == 1:
                dest_address = socket.inet_ntoa(await reader.read(4))
            elif address_type == 3:
                domain_length = ord(await reader.read(1))
                dest_address = (await reader.read(domain_length)).decode()
            elif address_type == 4:
                dest_address = socket.inet_ntop(socket.AF_INET6, await reader.read(16))
            else:
                writer.close(); return
            
            dest_port = struct.unpack("!H", await reader.read(2))[0]
            target_str = f"{dest_address}:{dest_port}"
            
            logger.debug(f"[{client_id}] Requested Tunnel -> {target_str}")

            # --- SINKHOLE LOGIC ---
            if address_type == 3 and is_blocked(dest_address):
                logger.info(f"[!] BLOCKED: {dest_address}")
                logger.debug(f"[{client_id}] Closing connection due to block rule.")
                writer.write(struct.pack("!BBBBIH", 5, 2, 0, 1, 0, 0))
                await writer.drain(); writer.close(); return
            # ----------------------

            # Step 3: Tunnel
            try:
                remote_reader, remote_writer = await asyncio.wait_for(
                    asyncio.open_connection(dest_address, dest_port), timeout=10
                )
                logger.debug(f"[{client_id}] Remote socket connected.")
                writer.write(struct.pack("!BBBBIH", 5, 0, 0, 1, 0, 0))
                await writer.drain()
            except Exception as e:
                logger.debug(f"[{client_id}] Connection Failed: {e}")
                writer.write(struct.pack("!BBBBIH", 5, 4, 0, 1, 0, 0))
                await writer.drain(); writer.close(); return

            logger.info(f"[*] Tunnel Established: {client_id} <-> {target_str}")

            # Step 4: Relay
            async def relay(src, dst, direction):
                try:
                    while True:
                        data = await src.read(16384)
                        if not data: break
                        dst.write(data)
                        await dst.drain()
                except Exception as e:
                    logger.debug(f"[{client_id}] {direction} Pipe Error: {e}")
                finally: 
                    try: dst.close(); await dst.wait_closed()
                    except: pass

            await asyncio.gather(
                relay(reader, remote_writer, "Upload"), 
                relay(remote_reader, writer, "Download"), 
                return_exceptions=True
            )
            logger.debug(f"[{client_id}] Tunnel closed cleanly.")

        except Exception as e:
            logger.debug(f"[{client_id}] General Handler Error: {e}")
        finally:
            writer.close()
            try: await writer.wait_closed()
            except: pass

    async def run(self):
        asyncio.create_task(update_blocklist())
        
        server = await asyncio.start_server(self.handle_client, self.host, self.port, reuse_address=True)
        logger.info(f"[*] pySOCKS5 DEBUG Active on {self.host}:{self.port}")
        logger.info(f"[*] Extensive logs writing to: pysocks5_debug.log")
        
        async with server:
            try: await server.serve_forever()
            except asyncio.CancelledError: pass
            finally: server.close(); await server.wait_closed()

if __name__ == '__main__':
    try: asyncio.run(SOCKS5Server().run())

    except KeyboardInterrupt: sys.exit(0)
