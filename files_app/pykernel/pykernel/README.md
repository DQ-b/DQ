# PyKernel — a teaching OS kernel in pure Python

A runnable simulation of an operating-system kernel. No real hardware — but the
**architecture** mirrors a real kernel, so you can study how the subsystems fit
together without drowning in C and hardware errata.

```
python boot.py roundrobin     # fair time-slicing
python boot.py priority       # priority preemption
```

## Layering (read in this order)

```
userland/programs.py     "user programs" — only know syscall numbers
        │  (traps via `yield sys_*()`)
        ▼
kernel/syscall/          the syscall interface (the privilege boundary)
        ▼
kernel/kernel.py         THE CORE: main loop, context switch, dispatch, ISRs
   ┌────┼────────────────┐
   ▼    ▼                ▼
mm/    sched/           ipc/        independent subsystems,
memory scheduler        channels    each knows only the kernel
   ▼
arch/cpu.py              the simulated "hardware": clock + interrupts
```

The one rule that keeps a big system readable: **subsystems don't import each
other.** `mm`, `sched`, and `ipc` are siblings that only ever talk to the
kernel core. The kernel is the single integration point. Trace any feature and
it always flows through `kernel.py`.

## What each file teaches

| File | Concept |
|------|---------|
| `arch/cpu.py` | clock interrupts, the hardware/software boundary |
| `kernel/process.py` | the PCB, process states & lifecycle |
| `kernel/mm/memory.py` | physical frames vs. virtual pages, demand paging, MMU translation |
| `kernel/sched/scheduler.py` | pluggable policy vs. mechanism (round-robin / priority) |
| `kernel/syscall/syscalls.py` | the userland↔kernel contract |
| `kernel/ipc/channels.py` | message passing, blocking & wakeups |
| `kernel/kernel.py` | how it all integrates: dispatch, preemption, context switch |

## How "execution" works

A program is a Python **generator**. Every `yield` is a context-switch boundary:
the process hands the CPU back to the kernel. A yielded
`('syscall', number, args)` is a trap. The kernel services it and `send()`s the
return value back into the generator on its next turn. That's the entire
mechanism — simple enough to read in one sitting, faithful enough to teach the
real ideas.

## Exercises (implement these to go deeper)

1. **Multi-level feedback queue (MLFQ)** — add a third scheduler class that
   demotes CPU-bound processes and boosts I/O-bound ones. Drop it in; the kernel
   shouldn't need changes (that's the test of good layering).
2. **A real recv()** — right now `recv` re-traps until a message exists. Make the
   kernel re-deliver the message directly to a woken process so it doesn't busy-loop.
3. **A page-cache / swap** — when `PhysicalMemory` runs out of frames, evict a
   page to a "disk" dict instead of raising `OutOfMemory`.
4. **A filesystem** — flesh out the empty `kernel/fs/` package: an in-memory
   inode table + `open/read/write/close` syscalls.
5. **wait()/zombie reaping** — let a parent `wait()` on a child and collect its
   exit code, properly transitioning ZOMBIE → reaped.
6. **SMP** — add a second `CPU` and a per-core run queue. Now you have to think
   about locking the shared scheduler state.

Start with #1 or #2 — they're self-contained and show you immediately whether
you understand the dispatch loop.
