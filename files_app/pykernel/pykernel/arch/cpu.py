"""
arch/cpu.py — The "hardware" layer.

In a real OS this would be silicon. Here we simulate a single CPU with:
  - a monotonic clock (ticks)
  - a set of registers (just a context blob per process)
  - an interrupt controller that the kernel registers handlers with

Everything above this file pretends this is real hardware and only talks to
it through the interfaces defined here. That boundary is the whole point:
the kernel never reaches "below" the arch layer.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional


# Interrupt vector numbers (like x86 IRQ lines, simplified).
IRQ_TIMER = 0      # raised every clock tick -> drives the scheduler
IRQ_SYSCALL = 0x80  # raised by a process executing a "syscall" instruction


@dataclass
class Registers:
    """A process's saved CPU context. Real CPUs have rax/rbx/rip/rsp/etc.
    We keep an instruction pointer and a general-purpose scratch dict."""
    ip: int = 0                      # instruction pointer (index into program)
    gp: Dict[str, object] = field(default_factory=dict)  # general purpose
    syscall_no: Optional[int] = None
    syscall_args: tuple = ()
    syscall_ret: object = None


class CPU:
    """A single simulated processor core."""

    def __init__(self) -> None:
        self.ticks: int = 0
        self._handlers: Dict[int, Callable[[], None]] = {}
        self.current_context: Optional[Registers] = None
        self.halted: bool = False

    # --- interrupt controller ------------------------------------------------
    def register_interrupt(self, irq: int, handler: Callable[[], None]) -> None:
        """Kernel calls this at boot to wire up its ISRs."""
        self._handlers[irq] = handler

    def raise_interrupt(self, irq: int) -> None:
        """Fire an interrupt. The CPU jumps to the registered handler.
        If nothing is registered, the interrupt is lost (like an unmasked
        line with no ISR)."""
        handler = self._handlers.get(irq)
        if handler is not None:
            handler()

    # --- clock ---------------------------------------------------------------
    def tick(self) -> None:
        """Advance the clock by one unit and raise the timer interrupt.
        The scheduler hangs off IRQ_TIMER, so this is what makes the system
        'breathe'."""
        self.ticks += 1
        self.raise_interrupt(IRQ_TIMER)

    def halt(self) -> None:
        self.halted = True
