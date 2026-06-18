# -*- coding: utf-8 -*-
"""
通用字节级变异器。

不局限于 HTTP——给定一份"种子"输入（字节串），通过一系列经典变异策略
生成大量畸形样本，适合喂给本地解析器、文件格式处理器、协议实现等进行
模糊测试（配合崩溃监控，如 AddressSanitizer / 退出码检测）。

策略借鉴 AFL / radamsa 的常见手法：位翻转、字节翻转、算术增减、
插入边界整数、块删除/复制、注入"魔法值"等。
"""

from __future__ import annotations

import random
from dataclasses import dataclass

# 常被用作边界 / 触发条件的"有趣"值
INTERESTING_8 = [0, 1, 16, 32, 64, 100, 127, 128, 255]
INTERESTING_16 = [0, 128, 255, 256, 512, 1000, 1024, 4096, 32767, 32768, 65535]
INTERESTING_32 = [0, 1, 32768, 65535, 65536, 2147483647, 2147483648, 4294967295]
MAGIC_TOKENS = [
    b"%n%n%n", b"%s%s%s", b"$(id)", b"`id`", b"../../../../etc/passwd",
    b"\x00", b"\xff\xff\xff\xff", b"A" * 1024, b"' OR '1'='1", b"<script>",
    b"{{7*7}}", b"\r\n\r\n", b"-1", b"NaN", b"\xde\xad\xbe\xef",
]


@dataclass
class Mutator:
    """确定性可复现的变异器（固定 seed → 固定输出序列）。"""

    seed: int = 0

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)

    # --------------------------- 单步策略 ---------------------------- #
    def bit_flip(self, data: bytes) -> bytes:
        if not data:
            return data
        b = bytearray(data)
        idx = self.rng.randrange(len(b))
        b[idx] ^= 1 << self.rng.randrange(8)
        return bytes(b)

    def byte_flip(self, data: bytes) -> bytes:
        if not data:
            return data
        b = bytearray(data)
        idx = self.rng.randrange(len(b))
        b[idx] ^= 0xFF
        return bytes(b)

    def arith(self, data: bytes) -> bytes:
        if not data:
            return data
        b = bytearray(data)
        idx = self.rng.randrange(len(b))
        delta = self.rng.randint(-35, 35)
        b[idx] = (b[idx] + delta) & 0xFF
        return bytes(b)

    def insert_interesting(self, data: bytes) -> bytes:
        b = bytearray(data)
        pool = INTERESTING_8 + INTERESTING_16 + INTERESTING_32
        val = self.rng.choice(pool)
        width = 1 if val <= 0xFF else (2 if val <= 0xFFFF else 4)
        chunk = val.to_bytes(width, self.rng.choice(["little", "big"]), signed=False)
        pos = self.rng.randrange(len(b) + 1)
        b[pos:pos] = chunk
        return bytes(b)

    def insert_magic(self, data: bytes) -> bytes:
        b = bytearray(data)
        token = self.rng.choice(MAGIC_TOKENS)
        pos = self.rng.randrange(len(b) + 1)
        b[pos:pos] = token
        return bytes(b)

    def delete_block(self, data: bytes) -> bytes:
        if len(data) < 2:
            return data
        b = bytearray(data)
        n = self.rng.randint(1, max(1, len(b) // 4))
        pos = self.rng.randrange(len(b) - n + 1)
        del b[pos:pos + n]
        return bytes(b)

    def duplicate_block(self, data: bytes) -> bytes:
        if not data:
            return data
        b = bytearray(data)
        n = self.rng.randint(1, max(1, len(b) // 4))
        pos = self.rng.randrange(len(b) - n + 1) if len(b) > n else 0
        chunk = b[pos:pos + n]
        insert_at = self.rng.randrange(len(b) + 1)
        b[insert_at:insert_at] = chunk
        return bytes(b)

    def truncate(self, data: bytes) -> bytes:
        if not data:
            return data
        return data[: self.rng.randrange(len(data) + 1)]

    STRATEGIES = (
        "bit_flip", "byte_flip", "arith", "insert_interesting",
        "insert_magic", "delete_block", "duplicate_block", "truncate",
    )

    # --------------------------- 组合生成 ---------------------------- #
    def mutate(self, data: bytes, *, rounds: int = 1) -> bytes:
        """对 ``data`` 施加 ``rounds`` 次随机策略。"""
        out = data
        for _ in range(max(1, rounds)):
            strategy = getattr(self, self.rng.choice(self.STRATEGIES))
            out = strategy(out)
        return out

    def generate(self, seed_data: bytes, count: int, *, max_rounds: int = 3):
        """惰性产出 ``count`` 个变异样本。"""
        for _ in range(count):
            rounds = self.rng.randint(1, max_rounds)
            yield self.mutate(seed_data, rounds=rounds)
