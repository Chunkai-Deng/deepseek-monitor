"""DeepSeek API HTTP client for balance and usage endpoints."""

import logging
from datetime import datetime, timedelta, timezone

import requests

from usage_model import BalanceInfo, UsageData

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Raised when the DeepSeek API returns an error."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class DeepSeekClient:
    """HTTP client for DeepSeek API balance and usage endpoints."""

    BASE_URL = "https://api.deepseek.com"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "DeepSeekUsageMonitor/1.0",
            }
        )

    def _headers(self) -> dict:
        if not self.api_key:
            raise ApiError("API key not configured", status_code=None)
        return {"Authorization": f"Bearer {self.api_key}"}

    def fetch_balance(self) -> BalanceInfo:
        """Fetch account balance from GET /user/balance."""
        try:
            resp = self.session.get(
                f"{self.BASE_URL}/user/balance",
                headers=self._headers(),
                timeout=15,
            )

            if resp.status_code == 401:
                raise ApiError("Invalid API key", status_code=401)
            if resp.status_code == 429:
                raise ApiError("Rate limited — retry later", status_code=429)
            if resp.status_code != 200:
                raise ApiError(
                    f"Balance API returned {resp.status_code}: {resp.text[:200]}",
                    status_code=resp.status_code,
                )

            data = resp.json()
            logger.debug("Balance response: %s", data)
            return BalanceInfo.from_api_response(data)

        except requests.Timeout:
            raise ApiError("Balance API request timed out")
        except requests.ConnectionError as e:
            raise ApiError(f"Network error: {e}")

    def fetch_usage(self, days: int = 7) -> UsageData:
        """Fetch token usage from GET /v1/usage for the last N days."""
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)

        try:
            resp = self.session.get(
                f"{self.BASE_URL}/v1/usage",
                headers=self._headers(),
                params={
                    "start_time": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "end_time": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
                timeout=15,
            )

            if resp.status_code == 401:
                raise ApiError("Invalid API key", status_code=401)
            if resp.status_code == 404:
                raise ApiError("Usage endpoint not available (404)", status_code=404)
            if resp.status_code == 429:
                raise ApiError("Rate limited — retry later", status_code=429)
            if resp.status_code != 200:
                raise ApiError(
                    f"Usage API returned {resp.status_code}: {resp.text[:200]}",
                    status_code=resp.status_code,
                )

            data = resp.json()
            logger.debug("Usage response: %s", data)
            return UsageData.from_api_response(data)

        except requests.Timeout:
            raise ApiError("Usage API request timed out")
        except requests.ConnectionError as e:
            raise ApiError(f"Network error: {e}")

    def test_connection(self) -> bool:
        """Quick test: returns True if the API key is valid."""
        try:
            self.fetch_balance()
            return True
        except ApiError:
            return False
