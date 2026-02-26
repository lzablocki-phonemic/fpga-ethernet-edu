"""
Ethernet Packet Sniffer with Scapy parsing and pcap export.

Works with any cocotbext-eth sink (XGMII, GMII, etc.) that supports
recv() and get_payload(). Runs as a cocotb background coroutine,
captures all frames, logs readable per-packet summaries, and can
export to Wireshark-compatible .pcap files.
"""

import cocotb

from scapy.layers.l2 import Ether, ARP
from scapy.layers.inet import IP, UDP
from scapy.utils import wrpcap


class EthSniffer:
    """Background Ethernet packet sniffer with Scapy parsing and pcap export.

    Works with XgmiiSink, GmiiSink, or any cocotbext-eth sink.
    """

    def __init__(self, name, sink, log):
        self.name = name
        self.sink = sink
        self.log = log
        self.packets = []       # list of Scapy Ether packets
        self.frame_count = 0
        self._running = True
        self._task = cocotb.start_soon(self._run())

    async def _run(self):
        while self._running:
            frame = await self.sink.recv()
            raw = bytes(frame.get_payload())
            self.frame_count += 1
            ts_ns = frame.sim_time_start or 0
            ts_us = ts_ns / 1000.0

            try:
                pkt = Ether(raw)
                self.packets.append(pkt)
                # Build readable summary
                summary = pkt.summary()
                detail = f"#{self.frame_count:3d} @ {ts_us:10.2f}us  {summary}"

                if ARP in pkt:
                    a = pkt[ARP]
                    detail += f"  [op={a.op} {a.psrc}->{a.pdst}]"
                elif IP in pkt and UDP in pkt:
                    detail += (f"  [{pkt[IP].src}:{pkt[UDP].sport}"
                               f" -> {pkt[IP].dst}:{pkt[UDP].dport}"
                               f" len={pkt[UDP].len}]")
                elif IP in pkt:
                    detail += f"  [{pkt[IP].src} -> {pkt[IP].dst} proto={pkt[IP].proto}]"

                self.log.info("[%s] %s", self.name, detail)
            except Exception as e:
                self.log.warning("[%s] #%d @ %.2fus  Failed to parse: %s",
                                 self.name, self.frame_count, ts_us, e)

    def stop(self):
        self._running = False

    def write_pcap(self, path):
        """Write all captured packets to a .pcap file."""
        if self.packets:
            wrpcap(path, self.packets)
            self.log.info("[%s] Saved %d packets to %s",
                          self.name, len(self.packets), path)
        else:
            self.log.info("[%s] No packets captured, skipping pcap", self.name)


# Backward-compatible alias
XgmiiSniffer = EthSniffer
