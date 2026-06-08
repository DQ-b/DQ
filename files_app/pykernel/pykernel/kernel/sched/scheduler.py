"""
kernel/sched/scheduler.py — CPU scheduling.

The scheduler decides which READY process runs next. We deliberately separate
*policy* (which process?) from *mechanism* (the run queue, context switching),
so you can swap algorithms without touching the kernel core. This is exactly
how Linux structures it ("scheduling classes": CFS, RT, deadline...).

Two policies provided:
  RoundRobinScheduler  - fair, each process gets an equal time slice (quantum)
  PriorityScheduler    - higher priority preempts lower; round-robin within a tier
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from collections import deque
from typing import Deque, Optional

from kernel.process import Process, State


class Scheduler(ABC):
    """Policy interface. The kernel only ever calls these four methods."""

    QUANTUM = 3  # ticks per time slice before forced preemption

    @abstractmethod
    def add(self, proc: Process) -> None:
        """A process became READY."""

    @abstractmethod
    def remove(self, proc: Process) -> None:
        """A process left the run queue (blocked/exited)."""

    @abstractmethod
    def pick_next(self) -> Optional[Process]:
        """Choose the next process to run, or None if the queue is empty."""

    def should_preempt(self, current: Process) -> bool:
        """Default time-slice policy: preempt after the quantum expires."""
        return current.quantum_used >= self.QUANTUM


class RoundRobinScheduler(Scheduler):
    def __init__(self) -> None:
        self._queue: Deque[Process] = deque()

    def add(self, proc: Process) -> None:
        proc.state = State.READY
        if proc not in self._queue:
            self._queue.append(proc)

    def remove(self, proc: Process) -> None:
        if proc in self._queue:
            self._queue.remove(proc)

    def pick_next(self) -> Optional[Process]:
        if not self._queue:
            return None
        return self._queue.popleft()


class PriorityScheduler(Scheduler):
    """Higher numeric priority runs first. Within a priority level, FIFO.
    A higher-priority arrival preempts a running lower-priority process."""

    def __init__(self) -> None:
        self._queues: dict[int, Deque[Process]] = {}

    def add(self, proc: Process) -> None:
        proc.state = State.READY
        q = self._queues.setdefault(proc.priority, deque())
        if proc not in q:
            q.append(proc)

    def remove(self, proc: Process) -> None:
        q = self._queues.get(proc.priority)
        if q and proc in q:
            q.remove(proc)

    def pick_next(self) -> Optional[Process]:
        for prio in sorted(self._queues.keys(), reverse=True):
            q = self._queues[prio]
            if q:
                return q.popleft()
        return None

    def should_preempt(self, current: Process) -> bool:
        # preempt if quantum expired OR a higher-priority process is waiting
        if current.quantum_used >= self.QUANTUM:
            return True
        for prio in self._queues:
            if prio > current.priority and self._queues[prio]:
                return True
        return False
