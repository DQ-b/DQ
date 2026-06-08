"""
kernel/process.py — The process abstraction (the PCB).

A process is the kernel's bookkeeping record around a running program.
Real kernels store this in a 'task_struct' (Linux) or 'proc' (BSD). Ours
holds the same essentials: pid, state, saved CPU context, its address space,
and a generator that represents the actual executing code.

We model "a program" as a Python generator. Each time it `yield`s, that's the
process voluntarily/involuntarily giving the CPU back to the kernel — i.e. a
context switch boundary. A yielded value of the form ('syscall', no, args)
is how userland asks the kernel to do something.
"""

from __future__ import annotations
from enum import Enum, auto
from typing import Generator, Optional

from arch.cpu import Registers
from kernel.mm.memory import AddressSpace


class State(Enum):
    NEW = auto()
    READY = auto()       # runnable, waiting for the CPU
    RUNNING = auto()     # currently on the CPU
    BLOCKED = auto()     # waiting on I/O / a resource
    ZOMBIE = auto()      # finished, exit code not yet reaped
    TERMINATED = auto()


# A program is a generator yielding either:
#   None                       -> "I'm yielding the CPU, reschedule me"
#   ('syscall', no, args...)   -> "perform this syscall for me"
Program = Generator


class Process:
    _next_pid = 1

    def __init__(self, name: str, program: Program, addr_space: AddressSpace,
                 priority: int = 0) -> None:
        self.pid = Process._next_pid
        Process._next_pid += 1

        self.name = name
        self.state = State.NEW
        self.priority = priority

        self.regs = Registers()
        self.addr_space = addr_space
        self.program = program

        self.exit_code: Optional[int] = None
        self.parent: Optional["Process"] = None
        self.wait_channel: Optional[str] = None  # what we're blocked on

        # scheduling accounting
        self.cpu_ticks = 0      # total ticks consumed
        self.quantum_used = 0   # ticks used in current time slice

    def __repr__(self) -> str:
        return f"<Process {self.pid}:{self.name} {self.state.name}>"
