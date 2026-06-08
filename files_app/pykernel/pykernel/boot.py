"""
boot.py — System entry point (the "bootloader" + init).

Run: python boot.py [roundrobin|priority]

This assembles the machine, loads the scheduler policy, spawns a set of init
processes, and starts the kernel. Watching the interleaved output is the whole
point — you can see preemption, sleeping, memory reclamation and IPC happen.
"""

import sys

from kernel.kernel import Kernel
from kernel.sched.scheduler import RoundRobinScheduler, PriorityScheduler
from userland.programs import (
    hello_program, memory_program, sleeper_program,
    producer_program, consumer_program, forker_program,
)


def main() -> None:
    policy = sys.argv[1] if len(sys.argv) > 1 else "roundrobin"
    scheduler = PriorityScheduler() if policy == "priority" else RoundRobinScheduler()

    print("=" * 64)
    print(f"  PyKernel booting  (scheduler: {policy})")
    print("=" * 64)

    k = Kernel(scheduler=scheduler, total_frames=64, verbose=True)

    # init: spawn the initial process set. Priorities only matter for the
    # priority scheduler; round-robin ignores them.
    k.spawn("hello",    hello_program(),    priority=1)
    k.spawn("memory",   memory_program(),   priority=2)
    k.spawn("sleeper",  sleeper_program(),  priority=1)
    k.spawn("producer", producer_program(), priority=3)
    k.spawn("consumer", consumer_program(), priority=3)
    k.spawn("forker",   forker_program(),   priority=1)

    k.run(max_ticks=500)

    print("=" * 64)
    print("  shutdown report")
    print("=" * 64)
    for pid in sorted(k.processes):
        p = k.processes[pid]
        print(f"  pid {pid:>2} {p.name:<14} state={p.state.name:<11} "
              f"exit={p.exit_code} cpu_ticks={p.cpu_ticks}")
    print(f"  physical frames free: {k.phys.free_count}/{k.phys.total_frames}")


if __name__ == "__main__":
    main()
