"""
Keyence VS-series Data Output TCP listener.

The Keyence camera acts as a TCP CLIENT — it connects to us after each
inspection and pushes a result frame.  This module starts an asyncio TCP
server that accepts those connections, parses the payload, and keeps the
latest result in memory for the rest of the application to read.

Typical VS-series output over TCP (ASCII mode):
  - Each inspection sends one frame terminated with CR+LF ("\r\n")
  - Fields are comma-separated, configurable in VS Creator's Data Output tool
  - The first field is always the overall judgement: "OK" or "NG"
  - Example: "OK,1,0.9523\r\n"   (judgement, program_no, score)
  - Example: "NG,1,0.1234\r\n"

The listener is tolerant of unknown formats — it logs raw bytes so you can
inspect exactly what the camera sends and adjust _parse() if needed.

Configuration (input_config.yaml):
  input.live_camera.keyence_output_port  (default 9876)
"""

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared state (module-level singleton, thread/coroutine-safe via asyncio)
# ---------------------------------------------------------------------------

class _State:
    def __init__(self):
        self.pass_fail: Optional[str] = None   # "PASS" | "FAIL" | None
        self.raw: Optional[str] = None         # last raw payload string
        self.fields: list = []                 # parsed CSV fields
        self.timestamp: Optional[float] = None # time.time() of last result
        self.connection_count: int = 0         # total connections received


_state = _State()


def get_latest_result() -> dict:
    """Return the most recent camera output result (or empty dict if none yet)."""
    if _state.timestamp is None:
        return {}
    return {
        "pass_fail": _state.pass_fail,
        "raw": _state.raw,
        "fields": _state.fields,
        "timestamp": _state.timestamp,
        "connection_count": _state.connection_count,
    }


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _parse(payload: str) -> tuple[Optional[str], list]:
    """
    Parse one inspection result frame from the camera.

    Returns (pass_fail, fields) where pass_fail is "PASS", "FAIL", or None
    if the judgement field is not recognisable.
    """
    payload = payload.strip()
    if not payload:
        return None, []

    # The VS series always sends a comma-separated list; the first field is
    # the overall judgement.
    fields = [f.strip() for f in payload.split(",")]
    first = fields[0].upper() if fields else ""

    if first in ("OK", "PASS", "0"):
        pass_fail = "PASS"
    elif first in ("NG", "FAIL", "1"):
        pass_fail = "FAIL"
    else:
        # Unknown format — still return all fields, caller can inspect raw
        pass_fail = None
        logger.warning("keyence_listener: unrecognised judgement field %r in %r", first, payload)

    return pass_fail, fields


# ---------------------------------------------------------------------------
# Async TCP server
# ---------------------------------------------------------------------------

async def _handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    peer = writer.get_extra_info("peername")
    _state.connection_count += 1
    logger.info("keyence_listener: connection #%d from %s", _state.connection_count, peer)

    try:
        # Read the full frame.  VS cameras send one frame per connection and
        # then close, so we read until EOF.  Guard with a timeout so a stale
        # connection doesn't block indefinitely.
        raw_bytes = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        if not raw_bytes:
            logger.debug("keyence_listener: empty payload from %s", peer)
            return

        raw_str = raw_bytes.decode("ascii", errors="replace")
        logger.info("keyence_listener: received %d bytes from %s: %r", len(raw_bytes), peer, raw_str)

        pass_fail, fields = _parse(raw_str)
        _state.pass_fail = pass_fail
        _state.raw = raw_str.strip()
        _state.fields = fields
        _state.timestamp = time.time()

        logger.info(
            "keyence_listener: parsed → pass_fail=%s  fields=%s",
            pass_fail, fields,
        )

    except asyncio.TimeoutError:
        logger.warning("keyence_listener: read timeout from %s", peer)
    except Exception as exc:
        logger.error("keyence_listener: error handling client %s: %s", peer, exc)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def start_listener(port: int = 9876, host: str = "0.0.0.0") -> asyncio.Server:
    """
    Start the TCP server.  Returns the asyncio.Server object (already
    running as a background task — no need to await serve_forever()).

    Call this once from the FastAPI startup event:
        server = await keyence_listener.start_listener(port=9876)
    """
    server = await asyncio.start_server(_handle_client, host, port)
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    logger.info("keyence_listener: TCP server listening on %s", addrs)
    # Schedule serve_forever() as a background task so it doesn't block startup
    asyncio.ensure_future(server.serve_forever())
    return server
