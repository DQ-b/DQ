"""
kernel/syscall/syscalls.py — The system call interface.

This is the *only* legitimate door between userland and the kernel. A process
can't touch memory it doesn't own, spawn a process, or do I/O directly — it
asks the kernel by raising a syscall, and the kernel decides whether/how to
service it. That privilege boundary is the heart of OS design.

Each syscall has a number (like Linux's syscall table). The kernel installs
itself as the handler set at boot. Userland never imports the kernel; it only
knows syscall numbers.
"""

from __future__ import annotations

# Syscall numbers (compare: /usr/include/asm/unistd_64.h)
SYS_WRITE = 1     # write(text)            -> print to console
SYS_GETPID = 2    # getpid()               -> own pid
SYS_FORK = 3      # fork(child_program)    -> spawn child, return child pid
SYS_EXIT = 4      # exit(code)             -> terminate self
SYS_SLEEP = 5     # sleep(ticks)           -> block for N ticks
SYS_YIELD = 6     # yield()                -> voluntarily give up the CPU
SYS_SEND = 7      # send(channel, msg)     -> IPC: enqueue a message
SYS_RECV = 8      # recv(channel)          -> IPC: block until a message
SYS_BRK = 9       # brk(vaddr, value)      -> grow heap / write memory


# Convenience wrappers used by userland programs. Each just packages a syscall
# request that the program `yield`s back to the kernel. This is what a libc
# stub does: turn a function call into a trap.
def sys_write(text):       return ('syscall', SYS_WRITE, (text,))
def sys_getpid():          return ('syscall', SYS_GETPID, ())
def sys_fork(program):     return ('syscall', SYS_FORK, (program,))
def sys_exit(code=0):      return ('syscall', SYS_EXIT, (code,))
def sys_sleep(ticks):      return ('syscall', SYS_SLEEP, (ticks,))
def sys_yield():           return ('syscall', SYS_YIELD, ())
def sys_send(chan, msg):   return ('syscall', SYS_SEND, (chan, msg))
def sys_recv(chan):        return ('syscall', SYS_RECV, (chan,))
def sys_brk(vaddr, value): return ('syscall', SYS_BRK, (vaddr, value))
