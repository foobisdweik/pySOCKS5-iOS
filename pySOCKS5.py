import asyncio
import socket
import struct
import sys
import os
import time
import ctypes
import traceback
import wave
from objc_util import ObjCClass, NSURL, ns, on_main_thread, c_void_p, sel

# =========================================================================
# [PHASE 1] STABLE TOGGLES (These work on iOS 26.3 / iPhone 16 Family)
#... mostly.
# =========================================================================
ENABLE_IPV6          = True   # Support IPv6 requests from OMEN
LOW_LATENCY_MODE     = True   # Disable Nagle's Algorithm (TCP_NODELAY)
HIGH_THROUGHPUT_MODE  = True   # Maximize buffer sizes for A18 SOC
AUDIO_HEARTBEAT      = True   # Play silent hum to prevent iOS sleep
VERBOSE_LOGGING      = True   # Show [CONN] requests in console
LISTEN_PORT          = 9999   # Port for Proxifier to connect to

# =================================================================
# [PHASE 2] EXPERIMENTAL/LEGACY (DO NOT ENABLE - FOR FUTURE DEVS)
# These features represent failed persistence attempts on iOS 26.3
# =================================================================
ENABLE_MIC_PERSISTENCE = False  # Status: UNSTABLE. No UI prompt granted.
ENABLE_LOC_PERSISTENCE = False  # Status: DEFUNCT. Permissions don't stop sleep.
FORCE_CPU_HIGH_PERF    = False  # Status: RISKY. Triggers thermal throttling.

# --- CONFIG & PATHS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HUM_FILE = os.path.join(SCRIPT_DIR, "background_hum.wav")
LOG_FILE = os.path.join(SCRIPT_DIR, "proxy_crash_log.txt")
HOTSPOT_GATEWAY = "172.20.10.1"

# Globals for memory retention
audio_player = None
proxy_instance = None
main_loop = None
_thunk_ref = None
_literal_ref = None

# -----------------------------------------------------------------
# [TOOL] SILENT WAV GENERATOR
# -----------------------------------------------------------------
def ensure_hum_exists():
    """Checks for background_hum.wav and generates it if missing."""
    if not os.path.exists(HUM_FILE):
        print(f"[INIT] {HUM_FILE} not found. Generating...")
        try:
            with wave.open(HUM_FILE, 'wb') as wav_file:
                wav_file.setnchannels(1)     # Mono
                wav_file.setsampwidth(2)     # 16-bit
                wav_file.setframerate(44100) # CD Quality
                # 10 seconds of digital zero (silence)
                silent_frames = b'\x00' * (44100 * 2 * 10)
                wav_file.writeframes(silent_frames)
            print(f"[INIT] Success: {HUM_FILE} created.")
        except Exception as e:
            print(f"[ERROR] Failed to generate hum file: {e}")

# -----------------------------------------------------------------
# [EXPERIMENTAL] LEGACY CODE BLOCKS (INERT)
# -----------------------------------------------------------------
def start_mic_loop():
    """LEGACY: Attempted to use microphone input to force background time."""
    # Logic: iOS 26.3 often denies mic access to background scripts 
    # without a specific entitlement we cannot currently spoof.
    pass

def start_location_pinger():
    """LEGACY: Attempted to use 'Always' location to keep process alive."""
    # Logic: CoreLocation 'Always' permission is granted, but the 
    # kernel suspends the interpreter regardless after ~30s of idle.
    pass

# -----------------------------------------------------------------
# [STABLE] CORE LOGIC & NETWORKING
# -----------------------------------------------------------------
def log_to_file(message, level="INFO"):
    if not VERBOSE_LOGGING and level == "CONN": return
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] [{level}] {message}\n"
    try:
        with open(LOG_FILE, 'a') as f: f.write(log_entry)
    except: pass
    print(log_entry.strip())

# --- NATIVE LOCK SCREEN LOGIC ---
class _block_descriptor(ctypes.Structure):
    _fields_ = [('reserved', ctypes.c_ulong), ('size', ctypes.c_ulong),
                ('copy_helper', ctypes.c_void_p), ('dispose_helper', ctypes.c_void_p),
                ('signature', ctypes.c_char_p)]

class _block_literal(ctypes.Structure):
    _fields_ = [('isa', ctypes.c_void_p), ('flags', ctypes.c_int),
                ('reserved', ctypes.c_int), ('invoke', ctypes.c_void_p),
                ('descriptor', ctypes.POINTER(_block_descriptor))]

def make_block(func, restype=None, argtypes=None):
    if argtypes is None: argtypes = []
    def thunk(block_ptr, *args): return func(*args)
    methtype = ctypes.CFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    _thunk_ptr = methtype(thunk)
    descriptor = _block_descriptor(0, ctypes.sizeof(_block_literal), None, None, None)
    lib = ctypes.CDLL(None)
    isa = ctypes.c_void_p.in_dll(lib, "_NSConcreteStackBlock")
    literal = _block_literal(ctypes.cast(ctypes.pointer(isa), ctypes.c_void_p),
                             (1 << 29), 0, ctypes.cast(_thunk_ptr, ctypes.c_void_p),
                             ctypes.pointer(descriptor))
    return _thunk_ptr, literal

def next_track_triggered(event_ptr):
    log_to_file("RECOVERY: Lock screen refresh triggered.", "EVENT")
    if proxy_instance and main_loop:
        main_loop.call_soon_threadsafe(lambda: asyncio.create_task(proxy_instance.manual_restart()))
    return 0 

@on_main_thread
def setup_lock_screen_controls():
    global _thunk_ref, _literal_ref
    try:
        command_center = ObjCClass('MPRemoteCommandCenter').sharedCommandCenter()
        next_cmd = command_center.nextTrackCommand()
        next_cmd.setEnabled_(True)
        _thunk_ref, _literal_ref = make_block(next_track_triggered, ctypes.c_int, [ctypes.c_void_p])
        block_void_p = ctypes.cast(ctypes.pointer(_literal_ref), ctypes.c_void_p)
        c = ctypes.CDLL(None)
        c.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        c.objc_msgSend.restype = ctypes.c_void_p
        c.objc_msgSend(next_cmd.ptr, sel('addTargetWithHandler:'), block_void_p)
        log_to_file("UI: Lock screen ready.", "INIT")
        update_lock_screen_status(f"Gateway: {HOTSPOT_GATEWAY}")
    except Exception:
        log_to_file(f"UI FATAL: {traceback.format_exc()}", "FATAL")

@on_main_thread
def update_lock_screen_status(status_text):
    try:
        center = ObjCClass('MPNowPlayingInfoCenter').defaultCenter()
        info = {'title': status_text, 'artist': 'Tuned SOCKS5 Proxy', 'playbackRate': 1.0}
        center.setNowPlayingInfo_(ns(info))
    except: pass

class SOCKS5Server:
    def __init__(self, port=LISTEN_PORT):
        self.host = ''
        self.port = port
        self.server = None

    async def manual_restart(self):
        log_to_file("Restarting server...", "RECOVERY")
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        await self.run()

    def _optimize_socket(self, sock):
        try:
            if LOW_LATENCY_MODE:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            if HIGH_THROUGHPUT_MODE:
                buf_size = 1048576 # 1MB
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, buf_size)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, buf_size)
        except: pass

    async def handle_client(self, reader, writer):
        try:
            sock = writer.get_extra_info('socket')
            if sock: self._optimize_socket(sock)
            header = await reader.read(2)
            if len(header) < 2: return
            ver, nmethods = struct.unpack("!BB", header)
            if nmethods > 0: await reader.read(nmethods)
            writer.write(struct.pack("!BB", 5, 0))
            await writer.drain()

            req = await reader.read(4)
            if len(req) < 4: return
            ver, cmd, _, addr_type = struct.unpack("!BBBB", req)
            
            addr = ""
            if addr_type == 1: # IPv4
                addr = socket.inet_ntoa(await reader.read(4))
            elif addr_type == 3: # Domain
                domain_len = ord(await reader.read(1))
                addr = (await reader.read(domain_len)).decode()
            elif addr_type == 4 and ENABLE_IPV6: # IPv6
                addr = socket.inet_ntop(socket.AF_INET6, await reader.read(16))
            else:
                writer.close(); return

            port_raw = await reader.read(2)
            if len(port_raw) < 2: return
            port = struct.unpack("!H", port_raw)[0]
            log_to_file(f"Request: {addr}:{port}", "CONN")

            try:
                r_reader, r_writer = await asyncio.wait_for(
                    asyncio.open_connection(addr, port), timeout=10)
                remote_sock = r_writer.get_extra_info('socket')
                if remote_sock: self._optimize_socket(remote_sock)
                writer.write(struct.pack("!BBBBIH", 5, 0, 0, 1, 0, 0))
                await writer.drain()
                
                chunk = 262144 if HIGH_THROUGHPUT_MODE else 65536
                async def pipe(src, dst):
                    try:
                        while True:
                            data = await src.read(chunk)
                            if not data: break
                            dst.write(data)
                            await dst.drain()
                    except: pass
                    finally: dst.close()
                await asyncio.gather(pipe(reader, r_writer), pipe(r_reader, writer))
            except:
                writer.write(struct.pack("!BBBBIH", 5, 5, 0, 1, 0, 0))
                await writer.drain()
        except Exception: pass
        finally:
            writer.close()

    async def run(self):
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port, reuse_address=True)
        log_to_file(f"SOCKS5 LIVE on *:{self.port}", "NET")
        async with self.server: await self.server.serve_forever()

def start_audio_keep_alive():
    global audio_player
    if not AUDIO_HEARTBEAT: return
    try:
        session = ObjCClass('AVAudioSession').sharedInstance()
        session.setCategory_error_('AVAudioSessionCategoryPlayback', None)
        session.setActive_error_(True, None)
        if os.path.exists(HUM_FILE):
            url = NSURL.fileURLWithPath_(ns(HUM_FILE))
            audio_player = ObjCClass('AVAudioPlayer').alloc().initWithContentsOfURL_error_(url, None)
            audio_player.setNumberOfLoops_(-1)
            audio_player.setVolume_(0.01)
            audio_player.play()
            log_to_file("Audio Keep-Alive active.")
    except: pass

async def delayed_start():
    log_to_file("Waiting for stability (3s)...", "INIT")
    await asyncio.sleep(3)
    setup_lock_screen_controls()

async def main():
    global proxy_instance, main_loop
    main_loop = asyncio.get_running_loop()
    proxy_instance = SOCKS5Server()
    asyncio.create_task(delayed_start())
    await proxy_instance.run()

if __name__ == '__main__':
    log_to_file("--- SESSION START ---", "INIT")
    ensure_hum_exists() # Check/Generate hum file first
    start_audio_keep_alive()
    try: asyncio.run(main())
    except KeyboardInterrupt: sys.exit(0)
