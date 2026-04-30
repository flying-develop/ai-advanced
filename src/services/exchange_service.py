"""ExchangeService — fetches currency exchange rates from an external API."""

# stdlib
import logging
from typing import Optional

# third-party
import httpx

# local
from src.config import settings

logger = logging.getLogger(__name__)


class ExchangeServiceError(Exception):
    """Raised when the exchange rates API call fails."""

    pass


class ExchangeService:
    """Retrieves currency exchange rates via the exchangeratesapi.io-compatible API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
    ) -> None:
        self._api_key = api_key or settings.exchange_api_key.get_secret_value()
        self._api_url = api_url or settings.exchange_api_url

    async def get_rates(
        self,
        base: str,
        symbols: list[str],
    ) -> dict[str, float]:
        """Fetch exchange rates for the given base currency and target symbols.

        Args:
            base: ISO 4217 base currency code, e.g. "USD".
            symbols: List of target currency codes, e.g. ["EUR", "GBP", "RUB"].

        Returns:
            Mapping of currency code to exchange rate relative to base.

        Raises:
            ExchangeServiceError: On HTTP error, unexpected response shape, or timeout.
        """
        params = {
            "access_key": self._api_key,
            "base": base,
            "symbols": ",".join(symbols),
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self._api_url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            logger.error("Exchange API request timed out")
            raise ExchangeServiceError("Exchange API request timed out") from exc
        except httpx.HTTPStatusError as exc:
            logger.error("Exchange API HTTP error %s", exc.response.status_code)
            raise ExchangeServiceError(
                f"Exchange API HTTP error {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            logger.error("Exchange API connection error: %s", exc)
            raise ExchangeServiceError("Exchange API connection error") from exc

        if not data.get("success", True) or "rates" not in data:
            error_info = data.get("error", {})
            logger.error("Exchange API returned error: %s", error_info)
            raise ExchangeServiceError(f"Exchange API error: {error_info}")

        return dict(data["rates"])
