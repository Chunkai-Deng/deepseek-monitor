"""Data models for DeepSeek API responses."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class BalanceInfo:
    """Parsed balance information from GET /user/balance."""

    is_available: bool
    currency: str
    total_balance: float
    granted_balance: float
    topped_up_balance: float

    @classmethod
    def from_api_response(cls, data: dict) -> "BalanceInfo":
        """Parse the DeepSeek /user/balance JSON response."""
        info = data["balance_infos"][0]
        return cls(
            is_available=data.get("is_available", False),
            currency=info["currency"],
            total_balance=float(info["total_balance"]),
            granted_balance=float(info["granted_balance"]),
            topped_up_balance=float(info["topped_up_balance"]),
        )


@dataclass
class UsageData:
    """Parsed usage data from GET /v1/usage."""

    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    api_calls: int = 0
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None

    @classmethod
    def from_api_response(cls, data: dict) -> "UsageData":
        """Parse the DeepSeek /v1/usage JSON response.

        Uses defensive parsing since the exact response shape may vary.
        Logs raw data on first run so field mappings can be adjusted.
        """
        # Try known response shapes. The usage API may return:
        #   {"total_usage": [...], "total_tokens": N, ...}
        # or:
        #   {"data": {"total_tokens": N, ...}}
        # We try multiple paths gracefully.

        def _int(v) -> int:
            try:
                return int(v)
            except (TypeError, ValueError):
                return 0

        # Flatten: if data is wrapped in "data", unwrap it
        inner = data.get("data", data)

        return cls(
            total_tokens=_int(inner.get("total_tokens", 0)),
            prompt_tokens=_int(inner.get("prompt_tokens", 0)),
            completion_tokens=_int(inner.get("completion_tokens", 0)),
            api_calls=_int(inner.get("api_calls", 0)),
            period_start=None,
            period_end=None,
        )


@dataclass
class ApiStatus:
    """Overall status after a refresh cycle."""

    balance: Optional[BalanceInfo] = None
    usage: Optional[UsageData] = None
    balance_error: Optional[str] = None
    usage_error: Optional[str] = None
    last_refreshed: Optional[datetime] = None

    @property
    def has_any_data(self) -> bool:
        return self.balance is not None or self.usage is not None

    @property
    def is_healthy(self) -> bool:
        return self.balance is not None and self.balance.is_available
