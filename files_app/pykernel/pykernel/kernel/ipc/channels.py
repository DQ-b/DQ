"""
kernel/ipc/channels.py — Inter-process communication.

Processes are isolated by design (separate address spaces), so they can't
just share variables. They communicate through kernel-mediated channels —
message queues the kernel owns. This mirrors pipes / message queues / mailboxes
in real systems.

A recv() on an empty channel BLOCKS the calling process; a send() wakes any
process blocked waiting on that channel. The kernel drives the wakeups.
"""

from __future__ import annotations
from collections import deque
from typing import Deque, Dict, List

from kernel.process import Process


class ChannelManager:
    def __init__(self) -> None:
        self._messages: Dict[str, Deque[object]] = {}
        self._waiters: Dict[str, List[Process]] = {}

    def send(self, channel: str, msg: object) -> List[Process]:
        """Enqueue a message. Return the list of processes that were blocked
        on this channel and should now be woken (the kernel does the actual
        state transition)."""
        self._messages.setdefault(channel, deque()).append(msg)
        woken = self._waiters.pop(channel, [])
        return woken

    def try_recv(self, channel: str):
        """Return (got_message, message). If the queue is empty the caller
        must block."""
        q = self._messages.get(channel)
        if q:
            return True, q.popleft()
        return False, None

    def block_on(self, channel: str, proc: Process) -> None:
        self._waiters.setdefault(channel, []).append(proc)
