"""
kernel/kernel.py — The kernel core. This is where everything meets.

Responsibilities:
  - boot: wire interrupt handlers, create the idle/init process
  - the main loop: tick the clock, run the current process for one step,
    handle whatever it yields (a syscall, a voluntary yield, or completion)
  - context switching: save/restore process state around the CPU
  - syscall dispatch: turn a process's request into kernel action
  - timer ISR: enforce preemption (the scheduler's time slice)
  - sleep/IPC bookkeeping: move processes between READY and BLOCKED

The design rule: subsystems (mm, sched, ipc) don't know about each other.
They only know the kernel. The kernel is the integration point. That's what
keeps a large system understandable.
"""

from __future__ import annotations
from typing import Dict, List, Optional

from arch.cpu import CPU, IRQ_TIMER
from kernel.process import Process, State
from kernel.mm.memory import PhysicalMemory, AddressSpace
from kernel.sched.scheduler import Scheduler, RoundRobinScheduler
from kernel.ipc.channels import ChannelManager
from kernel.syscall import syscalls as sc


class Kernel:
    def __init__(self, scheduler: Optional[Scheduler] = None,
                 total_frames: int = 64, verbose: bool = True) -> None:
        self.cpu = CPU()
        self.phys = PhysicalMemory(total_frames)
        self.sched: Scheduler = scheduler or RoundRobinScheduler()
        self.ipc = ChannelManager()
        self.verbose = verbose

        self.processes: Dict[int, Process] = {}
        self.current: Optional[Process] = None

        # processes sleeping until cpu.ticks >= wake_tick
        self._sleepers: List[tuple[int, Process]] = []

        # syscall number -> bound handler method
        self._syscall_table = {
            sc.SYS_WRITE:  self._sys_write,
            sc.SYS_GETPID: self._sys_getpid,
            sc.SYS_FORK:   self._sys_fork,
            sc.SYS_EXIT:   self._sys_exit,
            sc.SYS_SLEEP:  self._sys_sleep,
            sc.SYS_YIELD:  self._sys_yield,
            sc.SYS_SEND:   self._sys_send,
            sc.SYS_RECV:   self._sys_recv,
            sc.SYS_BRK:    self._sys_brk,
        }

        self.cpu.register_interrupt(IRQ_TIMER, self._timer_isr)

    # ------------------------------------------------------------------ log
    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"[tick {self.cpu.ticks:>3}] {msg}")

    # --------------------------------------------------------------- process
    def spawn(self, name: str, program, priority: int = 0) -> Process:
        """Create a process: give it a fresh address space and enqueue it."""
        addr = AddressSpace(self.phys)
        proc = Process(name, program, addr, priority)
        self.processes[proc.pid] = proc
        self.sched.add(proc)
        self._log(f"spawned {proc!r}")
        return proc

    # ------------------------------------------------------------ main loop
    def run(self, max_ticks: int = 1000) -> None:
        """The kernel's heartbeat. Each iteration:
          1. pick a process if none is current
          2. advance the clock (fires the timer ISR -> may preempt)
          3. run the current process one step
          4. handle what it yielded
        Stops when no runnable work remains or the tick budget is exhausted."""
        self._log("kernel boot complete, entering main loop")

        while self.cpu.ticks < max_ticks:
            if self.current is None:
                self.current = self._dispatch()
                if self.current is None:
                    if self._sleepers:
                        # nothing READY but someone is sleeping -> idle-tick
                        self.cpu.tick()
                        self._wake_sleepers()
                        continue
                    break  # truly nothing to do: halt

            self.cpu.tick()              # timer ISR may flip a preempt flag
            self._wake_sleepers()
            self._run_one_step(self.current)

        self._log("main loop exited")
        self.cpu.halt()

    def _dispatch(self) -> Optional[Process]:
        proc = self.sched.pick_next()
        if proc is not None:
            proc.state = State.RUNNING
            proc.quantum_used = 0
            self.cpu.current_context = proc.regs
            self._log(f"dispatch -> {proc!r}")
        return proc

    def _run_one_step(self, proc: Process) -> None:
        """Resume the process until its next yield. The yielded value tells
        us why it gave up the CPU."""
        proc.cpu_ticks += 1
        proc.quantum_used += 1

        try:
            # resume the generator; feed back the previous syscall's return val
            request = proc.program.send(proc.regs.syscall_ret)
            proc.regs.syscall_ret = None
        except StopIteration:
            # the program ran off the end without calling exit() -> exit(0)
            self._terminate(proc, 0)
            return

        if request is None:
            # voluntary reschedule point ("yield the CPU")
            self._maybe_preempt(proc)
        elif isinstance(request, tuple) and request and request[0] == 'syscall':
            _, number, args = request
            self._handle_syscall(proc, number, args)
        else:
            self._maybe_preempt(proc)

    def _maybe_preempt(self, proc: Process) -> None:
        """Decide whether the running process keeps the CPU or yields it back
        to the run queue (cooperative + timer-driven)."""
        if proc.state != State.RUNNING:
            return  # a syscall already changed its state (blocked/exited)
        if self.sched.should_preempt(proc):
            self._log(f"preempt {proc!r} (quantum used {proc.quantum_used})")
            self.sched.add(proc)          # back to READY
            self.cpu.current_context = None
            self.current = None

    # ----------------------------------------------------------- interrupts
    def _timer_isr(self) -> None:
        """Timer interrupt service routine. In a real kernel this increments
        jiffies and marks the task for reschedule. Here the quantum check in
        _maybe_preempt does the work; this hook is where you'd add periodic
        accounting."""
        pass

    # ----------------------------------------------------------- sleep mgmt
    def _wake_sleepers(self) -> None:
        now = self.cpu.ticks
        still: List[tuple[int, Process]] = []
        for wake_tick, proc in self._sleepers:
            if now >= wake_tick:
                self._log(f"wake {proc!r} from sleep")
                self.sched.add(proc)
            else:
                still.append((wake_tick, proc))
        self._sleepers = still

    def _block(self, proc: Process, channel: str) -> None:
        proc.state = State.BLOCKED
        proc.wait_channel = channel
        self.cpu.current_context = None
        self.current = None

    # ----------------------------------------------------- syscall dispatch
    def _handle_syscall(self, proc: Process, number: int, args: tuple) -> None:
        handler = self._syscall_table.get(number)
        if handler is None:
            self._log(f"ENOSYS: unknown syscall {number} from {proc!r}")
            proc.regs.syscall_ret = -1
            return
        handler(proc, *args)

    def _sys_write(self, proc: Process, text: str) -> None:
        print(f"    (pid {proc.pid} {proc.name}) {text}")
        proc.regs.syscall_ret = len(text)

    def _sys_getpid(self, proc: Process) -> None:
        proc.regs.syscall_ret = proc.pid

    def _sys_fork(self, proc: Process, child_program) -> None:
        child = self.spawn(f"{proc.name}-child", child_program, proc.priority)
        child.parent = proc
        proc.regs.syscall_ret = child.pid

    def _sys_exit(self, proc: Process, code: int) -> None:
        self._terminate(proc, code)

    def _sys_sleep(self, proc: Process, ticks: int) -> None:
        wake = self.cpu.ticks + ticks
        proc.state = State.BLOCKED
        proc.wait_channel = f"sleep:{wake}"
        self._sleepers.append((wake, proc))
        self.cpu.current_context = None
        self.current = None
        self._log(f"{proc!r} sleeps until tick {wake}")

    def _sys_yield(self, proc: Process) -> None:
        self.sched.add(proc)
        self.cpu.current_context = None
        self.current = None

    def _sys_send(self, proc: Process, channel: str, msg: object) -> None:
        woken = self.ipc.send(channel, msg)
        for waiter in woken:
            self._log(f"{waiter!r} woken by message on '{channel}'")
            waiter.wait_channel = None
            self.sched.add(waiter)
        proc.regs.syscall_ret = 0

    def _sys_recv(self, proc: Process, channel: str) -> None:
        got, msg = self.ipc.try_recv(channel)
        if got:
            proc.regs.syscall_ret = msg
        else:
            self.ipc.block_on(channel, proc)
            self._block(proc, channel)
            self._log(f"{proc!r} blocks on recv('{channel}')")
            # NOTE: when re-dispatched, syscall_ret is still None, so the
            # program will need to recv again. For simplicity our demo
            # programs loop on recv until they get a value.

    def _sys_brk(self, proc: Process, vaddr: int, value: object) -> None:
        try:
            proc.addr_space.write(vaddr, value)
            proc.regs.syscall_ret = 0
        except Exception as e:  # OOM / segfault surface to userland as -1
            self._log(f"{proc!r} brk failed: {e}")
            proc.regs.syscall_ret = -1

    # ------------------------------------------------------------ terminate
    def _terminate(self, proc: Process, code: int) -> None:
        proc.exit_code = code
        proc.state = State.ZOMBIE
        proc.addr_space.teardown()       # reclaim memory
        self.sched.remove(proc)
        self.cpu.current_context = None
        self.current = None
        self._log(f"{proc!r} exited code={code}, freed memory "
                  f"(free frames now {self.phys.free_count})")
        proc.state = State.TERMINATED
