"""
Patched GMII Source and Sink for cocotb v2 compatibility.

cocotbext-eth's GmiiSink._run() uses `.value.integer` on single-bit Logic
signals, which doesn't exist in cocotb v2 (Logic has no .integer attribute).
This module provides drop-in replacements that use int() instead.
"""

import logging
import struct
import zlib

import cocotb
from cocotb.queue import Queue
from cocotb.triggers import RisingEdge, Timer, First, Event
from cocotb.utils import get_sim_time

from cocotbext.eth.gmii import GmiiFrame, GmiiSink as _GmiiSinkBase, GmiiSource as _GmiiSourceBase
from cocotbext.eth.constants import EthPre


def _safe_int(val):
    """Convert a cocotb signal value to int, handling both Logic and LogicArray."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


class GmiiSink(_GmiiSinkBase):
    """Patched GmiiSink that works with cocotb v2 Logic objects."""

    async def _run(self):
        frame = None
        self.active = False

        clock_edge_event = RisingEdge(self.clock)
        active_event = RisingEdge(self.dv)

        while True:
            await clock_edge_event

            if self.enable is None or self.enable.value:
                d_val = _safe_int(self.data.value)
                dv_val = _safe_int(self.dv.value)
                er_val = 0 if self.er is None else _safe_int(self.er.value)

                if frame is None:
                    if dv_val:
                        frame = GmiiFrame(bytearray(), [])
                        frame.sim_time_start = get_sim_time()
                else:
                    if not dv_val:
                        if self.mii_select is not None:
                            self.mii_mode = bool(_safe_int(self.mii_select.value))

                        if self.mii_mode:
                            odd = True
                            sync = False
                            b = 0
                            be = 0
                            data = bytearray()
                            error = []
                            for n, e in zip(frame.data, frame.error):
                                odd = not odd
                                b = (n & 0x0F) << 4 | b >> 4
                                be |= e
                                if not sync and b == EthPre.SFD:
                                    odd = True
                                    sync = True
                                if odd:
                                    data.append(b)
                                    error.append(be)
                                    be = 0
                            frame.data = data
                            frame.error = error

                        frame.compact()
                        frame.sim_time_end = get_sim_time()
                        self.log.info("RX frame: %s", frame)

                        self.queue_occupancy_bytes += len(frame)
                        self.queue_occupancy_frames += 1

                        self.queue.put_nowait(frame)
                        self.active_event.set()

                        frame = None

                if frame is not None:
                    if frame.sim_time_sfd is None and d_val in (EthPre.SFD, 0xD):
                        frame.sim_time_sfd = get_sim_time()

                    frame.data.append(d_val)
                    frame.error.append(er_val)

                if not dv_val:
                    await active_event


class GmiiSource(_GmiiSourceBase):
    """Patched GmiiSource for cocotb v2 (base class works, but alias for consistency)."""
    pass
