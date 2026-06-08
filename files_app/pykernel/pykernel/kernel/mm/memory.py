"""
kernel/mm/memory.py — Memory management subsystem.

Two layers, exactly like a real kernel:

  PhysicalMemory  -> a flat array of frames (think: actual RAM chips)
  AddressSpace    -> per-process page table mapping virtual pages to frames

The point of the split: every process believes it owns a clean, contiguous
address space starting at 0, but underneath, its pages are scattered across
whatever physical frames were free. The page table is the translation layer.
"""

from __future__ import annotations
from typing import Dict, List, Optional


PAGE_SIZE = 4096  # bytes per page, same as classic x86


class OutOfMemory(Exception):
    pass


class SegFault(Exception):
    """Raised when a process touches an unmapped virtual address."""


class PhysicalMemory:
    """The machine's RAM: a fixed pool of equally-sized frames."""

    def __init__(self, total_frames: int = 64) -> None:
        self.total_frames = total_frames
        # frame number -> page contents (a dict simulating bytes)
        self._frames: List[Optional[dict]] = [None] * total_frames
        self._free: List[int] = list(range(total_frames))

    def alloc_frame(self) -> int:
        if not self._free:
            raise OutOfMemory("no free physical frames")
        frame = self._free.pop()
        self._frames[frame] = {}
        return frame

    def free_frame(self, frame: int) -> None:
        self._frames[frame] = None
        self._free.append(frame)

    def read(self, frame: int, offset: int) -> object:
        return self._frames[frame].get(offset)

    def write(self, frame: int, offset: int, value: object) -> None:
        self._frames[frame][offset] = value

    @property
    def free_count(self) -> int:
        return len(self._free)


class AddressSpace:
    """A single process's virtual memory. Owns a page table that maps
    virtual page numbers -> physical frame numbers."""

    def __init__(self, phys: PhysicalMemory) -> None:
        self._phys = phys
        self._page_table: Dict[int, int] = {}  # vpage -> frame

    def map_page(self, vpage: int) -> None:
        """Allocate a physical frame and map a virtual page to it
        (lazy allocation: pages only get frames when first mapped)."""
        if vpage in self._page_table:
            return
        self._page_table[vpage] = self._phys.alloc_frame()

    def _translate(self, vaddr: int) -> tuple[int, int]:
        """Virtual address -> (frame, offset). The core MMU operation."""
        vpage, offset = divmod(vaddr, PAGE_SIZE)
        frame = self._page_table.get(vpage)
        if frame is None:
            raise SegFault(f"unmapped virtual address {vaddr} (page {vpage})")
        return frame, offset

    def read(self, vaddr: int) -> object:
        frame, offset = self._translate(vaddr)
        return self._phys.read(frame, offset)

    def write(self, vaddr: int, value: object) -> None:
        vpage = vaddr // PAGE_SIZE
        if vpage not in self._page_table:
            self.map_page(vpage)  # demand paging
        frame, offset = self._translate(vaddr)
        self._phys.write(frame, offset, value)

    def teardown(self) -> None:
        """Return all this process's frames to the physical pool (called on
        process exit). Without this you leak memory exactly like a real OS."""
        for frame in self._page_table.values():
            self._phys.free_frame(frame)
        self._page_table.clear()
