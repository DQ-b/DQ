# -*- coding: utf-8 -*-
"""模糊测试模块：通用变异器 + HTTP fuzz 引擎 + 内置载荷集。"""

from __future__ import annotations

from .engine import HttpFuzzer, FuzzResult
from .mutator import Mutator
from .request import RawRequest, parse_raw_request
from . import payloads

__all__ = [
    "HttpFuzzer", "FuzzResult", "Mutator", "RawRequest", "parse_raw_request", "payloads",
]
