"""
userland/programs.py — Example "user programs".

These run in userland: they never import the kernel. They only know the
syscall stubs. Each is a generator; every `yield` is a trap into the kernel.
This is the application's-eye view of the OS — exactly the contract a real
program has with libc + the kernel.
"""

from kernel.syscall.syscalls import (
    sys_write, sys_getpid, sys_fork, sys_exit,
    sys_sleep, sys_yield, sys_send, sys_recv, sys_brk,
)


def hello_program():
    """Trivial: print who I am, do a bit of work, exit."""
    pid = yield sys_getpid()
    yield sys_write(f"hello, I am pid {pid}")
    for i in range(3):
        yield sys_write(f"working... step {i}")
        yield sys_yield()          # be a good citizen, share the CPU
    yield sys_exit(0)


def memory_program():
    """Touch several pages of memory through brk(), forcing the MM subsystem
    to allocate physical frames. Demonstrates the virtual->physical mapping."""
    yield sys_write("allocating memory across several pages")
    for page in range(4):
        vaddr = page * 4096        # one address per page
        rc = yield sys_brk(vaddr, f"data-{page}")
        yield sys_write(f"wrote page {page} (brk rc={rc})")
    yield sys_exit(0)


def sleeper_program():
    """Block on a timer, proving the scheduler keeps running others meanwhile."""
    yield sys_write("going to sleep for 5 ticks")
    yield sys_sleep(5)
    yield sys_write("woke up!")
    yield sys_exit(0)


def producer_program():
    """IPC producer: send three messages on a channel, then exit."""
    for i in range(3):
        yield sys_write(f"producing item {i}")
        yield sys_send("work-queue", f"item-{i}")
        yield sys_yield()
    yield sys_send("work-queue", "DONE")
    yield sys_exit(0)


def consumer_program():
    """IPC consumer: pull from the channel until it sees DONE.
    Loops on recv because our simple recv re-traps until a message exists."""
    while True:
        msg = yield sys_recv("work-queue")
        if msg is None:
            yield sys_yield()      # nothing yet; let producer run
            continue
        if msg == "DONE":
            yield sys_write("consumer saw DONE, exiting")
            break
        yield sys_write(f"consumed {msg}")
    yield sys_exit(0)


def forker_program():
    """Spawn a child process via fork(), then exit."""
    pid = yield sys_getpid()
    yield sys_write(f"pid {pid} forking a child")
    child = yield sys_fork(hello_program())
    yield sys_write(f"forked child pid {child}")
    yield sys_exit(0)
