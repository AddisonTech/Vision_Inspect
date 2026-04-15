"""
Keyence VS-series EtherNet/IP result poller.

Polls Assembly Object instance 100 (camera → scanner) via explicit CIP
messaging (TCP port 44818).  No PLC or cyclic I/O connection required —
just a direct pycomm3 CIPDriver read on a 0.25-second interval.

Assembly 100 layout (VS series, confirmed empirically):
  byte[ 0]        bit 0 = Run mode active (1 = running)
  byte[ 2]        bit 1 = NG/FAIL result  (1 = FAIL, 0 = PASS)
                  bit 3 = END / inspection done
                  bit 4 = (result toggle / new-result flag)
  byte[ 3]        bit 2 = program loaded / ready
  bytes[20-23]    UINT32 LE = active program number
  bytes[24-27]    UINT32 LE = inspection count (increments each trigger)

Public API
----------
  start_poller(host, port=44818)  → asyncio.Task  (call from startup event)
  get_latest_result()             → dict
  is_connected()                  → bool
"""

import asyncio
import logging
import struct
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

class _State:
    def __init__(self):
        self.pass_fail: Optional[str] = None   # "PASS" | "FAIL" | None
        self.raw_bytes: Optional[bytes] = None
        self.inspection_count: int = 0
        self.program_number: int = 0
        self.run_mode: bool = False
        self.timestamp: Optional[float] = None
        self.connected: bool = False


_state = _State()
_task: Optional[asyncio.Task] = None


def get_latest_result() -> dict:
    if _state.timestamp is None:
        return {}
    return {
        "pass_fail":        _state.pass_fail,
        "inspection_count": _state.inspection_count,
        "program_number":   _state.program_number,
        "run_mode":         _state.run_mode,
        "timestamp":        _state.timestamp,
        "connected":        _state.connected,
    }


def is_connected() -> bool:
    return _state.connected


# ---------------------------------------------------------------------------
# Assembly decoder
# ---------------------------------------------------------------------------

def _decode(data: bytes) -> dict:
    """
    Parse Assembly 100.  Returns dict with run_mode, pass_fail,
    inspection_count, program_number.
    """
    if len(data) < 28:
        return {}

    run_mode        = bool(data[0] & 0x01)
    fail_bit        = bool(data[2] & 0x02)   # bit 1 of byte 2 = NG
    pass_fail       = "FAIL" if fail_bit else "PASS"
    program_number  = struct.unpack_from("<I", data, 20)[0]
    inspection_count = struct.unpack_from("<I", data, 24)[0]

    return {
        "run_mode":        run_mode,
        "pass_fail":       pass_fail,
        "inspection_count": inspection_count,
        "program_number":  program_number,
    }


# ---------------------------------------------------------------------------
# Async poller
# ---------------------------------------------------------------------------

async def _poll_loop(host: str, port: int, interval: float = 0.25):
    """
    Open a CIP session to the camera and poll Assembly 100 continuously.
    Reconnects automatically on any error.
    """
    from pycomm3 import CIPDriver, Services  # imported here to keep startup fast

    last_count = -1

    while True:
        try:
            logger.info("keyence_eip: connecting to %s:%d …", host, port)

            # CIPDriver is synchronous — run in executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()

            def _open_and_poll():
                driver = CIPDriver(f"{host}:{port}")
                driver.open()
                return driver

            driver = await loop.run_in_executor(None, _open_and_poll)
            _state.connected = True
            logger.info("keyence_eip: CIP session open")

            try:
                while True:
                    def _read():
                        resp = driver.generic_message(
                            service=Services.get_attribute_single,
                            class_code=b'\x04',
                            instance=100,
                            attribute=b'\x03',
                            data_type=None,
                            name='asm100',
                        )
                        return resp.value if resp and resp.value else None

                    raw = await loop.run_in_executor(None, _read)

                    if raw:
                        decoded = _decode(raw)
                        if decoded:
                            new_count = decoded["inspection_count"]
                            _state.run_mode = decoded["run_mode"]
                            _state.program_number = decoded["program_number"]
                            _state.connected = True

                            if new_count != last_count:
                                _state.pass_fail = decoded["pass_fail"]
                                _state.inspection_count = new_count
                                _state.raw_bytes = raw
                                _state.timestamp = time.time()
                                last_count = new_count
                                logger.info(
                                    "keyence_eip: new result — %s  count=%d  prog=%d",
                                    decoded["pass_fail"], new_count, decoded["program_number"],
                                )

                    await asyncio.sleep(interval)

            finally:
                _state.connected = False
                try:
                    await loop.run_in_executor(None, driver.close)
                except Exception:
                    pass

        except asyncio.CancelledError:
            logger.info("keyence_eip: poller cancelled")
            _state.connected = False
            return
        except Exception as exc:
            logger.warning("keyence_eip: error (%s) — reconnecting in 5s", exc)
            _state.connected = False
            await asyncio.sleep(5)


def start_poller(host: str, port: int = 44818) -> asyncio.Task:
    """Start the EtherNet/IP poller as a background task."""
    global _task
    if _task and not _task.done():
        logger.warning("keyence_eip: poller already running")
        return _task
    _task = asyncio.ensure_future(_poll_loop(host, port))
    logger.info("keyence_eip: poller started → %s:%d", host, port)
    return _task


def stop_poller():
    global _task
    if _task and not _task.done():
        _task.cancel()
        _task = None


# ---------------------------------------------------------------------------
# Keep backward-compat shims so main.py import doesn't break
# ---------------------------------------------------------------------------
def start_client(host: str, port: int = 8500):
    """Deprecated — now uses EtherNet/IP poller instead."""
    logger.info("keyence: start_client() redirecting to EtherNet/IP poller on %s", host)
    return start_poller(host)
