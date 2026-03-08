"""
OpenAI Pricing Module
=====================

功能：
1. 定义 OpenAI 各模型的定价（picoUSD 精度）
2. 提供成本计算函数（文本模型、TTS）
3. 支持缓存 token 和推理 token 的精确计费

定价说明：
- 使用 picoUSD（1e-12 USD）存储，避免浮点误差
- Postgres BIGINT 足够（$10 = 10 * 10^12 = 10,000,000,000,000 picoUSD）
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

# 精度常量
PICO_PER_USD = 10**12  # 1 USD = 10^12 picoUSD
PICO_PER_1M = PICO_PER_USD // 1_000_000  # = 1,000,000 picoUSD per (USD/1M) per token/char


@dataclass(frozen=True)
class TextPricing:
    """文本模型定价（每百万 token 的 USD 价格）"""
    input_usd_per_1m: Decimal
    cached_input_usd_per_1m: Decimal
    output_usd_per_1m: Decimal

    @property
    def input_pico_per_token(self) -> int:
        """每个 input token 的 picoUSD 单价"""
        return int(self.input_usd_per_1m * PICO_PER_1M)

    @property
    def cached_input_pico_per_token(self) -> int:
        """每个 cached input token 的 picoUSD 单价"""
        return int(self.cached_input_usd_per_1m * PICO_PER_1M)

    @property
    def output_pico_per_token(self) -> int:
        """每个 output token 的 picoUSD 单价"""
        return int(self.output_usd_per_1m * PICO_PER_1M)


@dataclass(frozen=True)
class TtsPricing:
    """TTS 模型定价（每百万字符的 USD 价格）"""
    usd_per_1m_chars: Decimal

    @property
    def pico_per_char(self) -> int:
        """每个字符的 picoUSD 单价"""
        return int(self.usd_per_1m_chars * PICO_PER_1M)


@dataclass(frozen=True)
class TtsTokenPricing:
    """Token-based TTS 模型定价（gpt-4o-mini-tts）"""
    input_usd_per_1m: Decimal   # 输入 token 价格（每百万）
    output_usd_per_1m: Decimal  # 输出音频 token 价格（每百万）

    @property
    def input_pico_per_token(self) -> int:
        """每个 input token 的 picoUSD 单价"""
        return int(self.input_usd_per_1m * PICO_PER_1M)

    @property
    def output_pico_per_token(self) -> int:
        """每个 output audio token 的 picoUSD 单价"""
        return int(self.output_usd_per_1m * PICO_PER_1M)


# ============================================================================
# 文本模型定价表
# ============================================================================
# 来源：OpenAI 官方定价页面 https://openai.com/api/pricing/
# gpt-5.4: input $2.50/1M, cached $0.25/1M, output $15/1M
# gpt-4o-mini: input $0.15/1M, cached $0.075/1M, output $0.60/1M
# gpt-4.1: input $2.00/1M, cached $0.50/1M, output $8.00/1M
# gpt-4.1-mini: input $0.40/1M, cached $0.10/1M, output $1.60/1M

TEXT_PRICING: dict[str, TextPricing] = {
    # GPT-5.4 系列
    "gpt-5.4": TextPricing(
        Decimal("2.50"),
        Decimal("0.25"),
        Decimal("15.00")
    ),
    "gpt-5.4-chat-latest": TextPricing(
        Decimal("2.50"),
        Decimal("0.25"),
        Decimal("15.00")
    ),
    # GPT-4o-mini 系列
    "gpt-4o-mini": TextPricing(
        Decimal("0.15"),
        Decimal("0.075"),
        Decimal("0.60")
    ),
    # GPT-4.1 系列
    # 来源：https://openai.com/api/pricing/
    "gpt-4.1": TextPricing(
        Decimal("2.00"),
        Decimal("0.50"),
        Decimal("8.00")
    ),
    "gpt-4.1-mini": TextPricing(
        Decimal("0.40"),
        Decimal("0.10"),
        Decimal("1.60")
    ),
}


# ============================================================================
# TTS 模型定价表
# ============================================================================
# 来源：OpenAI 官方定价页面
# tts-1: $15/1M characters
# tts-1-hd: $30/1M characters

TTS_PRICING: dict[str, TtsPricing] = {
    "tts-1": TtsPricing(Decimal("15.00")),
    "tts-1-hd": TtsPricing(Decimal("30.00")),
}


# ============================================================================
# Token-based TTS 模型定价表（gpt-4o-mini-tts）
# ============================================================================
# 来源：OpenAI 官方定价页面
# gpt-4o-mini-tts: input $0.60/1M tokens, output $12.00/1M audio tokens

TTS_TOKEN_PRICING: dict[str, TtsTokenPricing] = {
    "gpt-4o-mini-tts": TtsTokenPricing(Decimal("0.60"), Decimal("12.00")),
}


# ============================================================================
# 辅助函数
# ============================================================================

# 匹配模型名称中的日期后缀，如 gpt-4o-mini-2024-07-18
_VERSION_SUFFIX = re.compile(r"-\d{4}-\d{2}-\d{2}$")


def normalize_model_name(model: str) -> str:
    """
    标准化模型名称

    处理：
    1. 移除 LangChain provider 前缀（如 "openai:gpt-5.4" -> "gpt-5.4"）
    2. 移除日期版本后缀（如 "gpt-4o-mini-2024-07-18" -> "gpt-4o-mini"）

    参数:
        model: 原始模型名称

    返回:
        标准化后的模型名称
    """
    # 移除 provider 前缀（如 "openai:gpt-5.4"）
    if ":" in model:
        model = model.split(":", 1)[1]

    # 移除日期版本后缀
    model = _VERSION_SUFFIX.sub("", model)

    return model


def compute_text_cost_pico(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
) -> int:
    """
    计算文本模型调用的成本（picoUSD）

    注意：
    - cached_input_tokens 是 input_tokens 的子集
    - 推理 tokens（reasoning tokens）计入 output_tokens（按 OpenAI 官方口径）

    参数:
        model: 模型名称
        input_tokens: 输入 token 总数
        output_tokens: 输出 token 总数（包含推理 tokens）
        cached_input_tokens: 缓存输入 token 数（input_tokens 的子集）

    返回:
        成本（picoUSD）

    异常:
        KeyError: 未知模型定价
    """
    base = normalize_model_name(model)
    p = TEXT_PRICING.get(base)
    if not p:
        raise KeyError(f"Unknown pricing for model={model} (normalized={base})")

    # cached_input_tokens 是 input_tokens 的子集；非缓存部分按 input 计费
    billable_input = max(0, input_tokens - cached_input_tokens)

    return (
        billable_input * p.input_pico_per_token
        + cached_input_tokens * p.cached_input_pico_per_token
        + output_tokens * p.output_pico_per_token
    )


def compute_tts_cost_pico(model: str, characters: int) -> int:
    """
    计算 TTS 调用的成本（picoUSD）

    参数:
        model: TTS 模型名称（如 "tts-1", "tts-1-hd"）
        characters: 字符数

    返回:
        成本（picoUSD）

    异常:
        KeyError: 未知 TTS 模型定价
    """
    p = TTS_PRICING.get(model)
    if not p:
        raise KeyError(f"Unknown TTS pricing model={model}")
    return characters * p.pico_per_char


def pico_to_usd_str(pico: int) -> str:
    """
    将 picoUSD 转换为 USD 字符串（保留 6 位小数）

    参数:
        pico: picoUSD 金额

    返回:
        USD 格式字符串（如 "0.001234"）
    """
    usd = Decimal(pico) / Decimal(PICO_PER_USD)
    return f"{usd:.6f}"


def usd_to_pico(usd: Decimal) -> int:
    """
    将 USD 转换为 picoUSD

    参数:
        usd: USD 金额

    返回:
        picoUSD 金额
    """
    return int(usd * PICO_PER_USD)


def estimate_max_cost_pico(
    model: str,
    estimated_input_tokens: int,
    max_output_tokens: int,
    cached_ratio: float = 0.0,
) -> int:
    """
    估算最大成本（用于预冻结 hold）

    参数:
        model: 模型名称
        estimated_input_tokens: 预估输入 token 数
        max_output_tokens: 最大输出 token 数
        cached_ratio: 预估缓存命中率（0.0 - 1.0），默认 0（保守估计）

    返回:
        估算最大成本（picoUSD）
    """
    cached_tokens = int(estimated_input_tokens * cached_ratio)

    return compute_text_cost_pico(
        model=model,
        input_tokens=estimated_input_tokens,
        output_tokens=max_output_tokens,
        cached_input_tokens=cached_tokens,
    )


def compute_tts_token_cost_pico(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> int:
    """
    计算 Token-based TTS 调用的成本（picoUSD）

    参数:
        model: TTS 模型名称（如 "gpt-4o-mini-tts"）
        input_tokens: 输入 token 数
        output_tokens: 输出音频 token 数

    返回:
        成本（picoUSD）

    异常:
        KeyError: 未知 TTS 模型定价
    """
    p = TTS_TOKEN_PRICING.get(model)
    if not p:
        raise KeyError(f"Unknown token-based TTS pricing model={model}")
    return (
        input_tokens * p.input_pico_per_token
        + output_tokens * p.output_pico_per_token
    )


def estimate_tts_token_max_cost_pico(model: str, text_length: int) -> int:
    """
    估算 Token-based TTS 的最大成本（用于预冻结）

    基于测试数据估算：
    - "Hello, this is a billing test." (31 chars) → input=8, output=69
    - 比例: input ≈ chars/4, output ≈ chars * 2.5

    使用保守估计：
    - max_input = text_length // 4 + 10 (buffer)
    - max_output = text_length * 4 (保守上界)

    参数:
        model: TTS 模型名称
        text_length: 文本字符数

    返回:
        估算最大成本（picoUSD）
    """
    p = TTS_TOKEN_PRICING.get(model)
    if not p:
        raise KeyError(f"Unknown token-based TTS pricing model={model}")

    max_input_tokens = text_length // 4 + 10
    max_output_tokens = text_length * 4

    return (
        max_input_tokens * p.input_pico_per_token
        + max_output_tokens * p.output_pico_per_token
    )
