"""
Lidl Ireland gift card balance checker.

Two modes:
1. Automated via balance-worker service (recommended) — uses Playwright to solve
   Friendly Captcha and retrieve balance.
2. Direct API call with pre-obtained captcha token (legacy).

Endpoint: POST https://www.lidl.ie/explore/giftyBalanceV2/gifty
Response: {"balance": {"amount": 5000, "currency": "EUR"}, "status": "ACTIVE"}
Balance amount is in cents (5000 = €50.00).
"""

import json
import os
import requests
from typing import Optional

from ..base import BaseBalanceChecker, BalanceResult


class LidlIEProvider(BaseBalanceChecker):
    """Lidl Ireland gift card balance checker."""

    display_name = "Lidl Ireland"
    base_url = "https://www.lidl.ie/c/gift-card-balance-check/s10073374"
    api_endpoint = "https://www.lidl.ie/explore/giftyBalanceV2/gifty"

    def __init__(self):
        self.balance_worker_url = os.environ.get(
            "BALANCE_WORKER_URL",
            "http://balance-worker:3001"  # default Docker network name
        )

    def check_balance(
        self, card_number: str, pin: str,
        frc_captcha_token: Optional[str] = None,
        **kwargs
    ) -> BalanceResult:
        """
        Check Lidl gift card balance.

        Uses the balance-worker service by default (Playwright automation
        handles Friendly Captcha). Falls back to direct API call if a
        captcha token is provided (legacy browser-based flow).

        Args:
            card_number: The gift card number (redeem_code)
            pin: The PIN/security code
            frc_captcha_token: Optional. If provided, calls the Lidl API
                               directly with this token.

        Returns:
            BalanceResult with balance or error
        """
        card_number = self.normalize_card_number(card_number)
        pin = self.normalize_pin(pin)

        if not card_number:
            return BalanceResult(success=False, error="Card number is required")
        if not pin:
            return BalanceResult(success=False, error="PIN is required")

        # If a captcha token was provided from the frontend, use the direct API
        if frc_captcha_token:
            return self._check_via_api(card_number, pin, frc_captcha_token)

        # Otherwise, use the automated balance-worker service
        return self._check_via_worker(card_number, pin)

    def _check_via_worker(self, card_number: str, pin: str) -> BalanceResult:
        """
        Check balance via the Playwright-powered balance-worker service.
        The worker handles Friendly Captcha automatically.
        """
        worker_url = f"{self.balance_worker_url}/check-lidl-balance"

        try:
            resp = requests.post(
                worker_url,
                json={"cardNumber": card_number, "pin": pin},
                timeout=300,  # captcha can take 15-60s + browser startup
            )

            if resp.status_code == 200:
                data = resp.json()
                return BalanceResult(
                    success=data.get("success", False),
                    balance=data.get("balance"),
                    currency=data.get("currency", "EUR"),
                    error=data.get("error"),
                )
            elif resp.status_code == 502:
                return BalanceResult(
                    success=False,
                    error="Balance worker is starting up. Please try again in a moment."
                )
            elif resp.status_code == 503:
                return BalanceResult(
                    success=False,
                    error="Balance worker is busy. Please try again shortly."
                )
            else:
                try:
                    err_data = resp.json()
                    return BalanceResult(
                        success=False,
                        error=err_data.get("error", f"Worker error (HTTP {resp.status_code})")
                    )
                except (ValueError, KeyError):
                    return BalanceResult(
                        success=False,
                        error=f"Balance worker returned HTTP {resp.status_code}"
                    )

        except requests.ConnectionError:
            return BalanceResult(
                success=False,
                error="Could not connect to balance worker. Is the service running?"
            )
        except requests.Timeout:
            return BalanceResult(
                success=False,
                error="Balance check timed out after 5 minutes. Please try again."
            )
        except requests.RequestException as e:
            return BalanceResult(
                success=False,
                error=f"Balance worker request failed: {str(e)}"
            )
        except (json.JSONDecodeError, ValueError) as e:
            return BalanceResult(
                success=False,
                error=f"Unexpected response from balance worker: {str(e)}"
            )

    def _check_via_api(
        self, card_number: str, pin: str,
        frc_captcha_token: str
    ) -> BalanceResult:
        """
        Check balance by calling the Lidl API directly with a pre-obtained
        Friendly Captcha token. Used when the frontend provides a token
        (legacy flow).
        """
        # Build API payload
        payload = {
            "cardNumber": card_number,
            "pinNumber": pin,
            "country": "IE",
            "locale": "en-IE",
            "frcCaptchaToken": frc_captcha_token,
        }

        headers = {
            "Content-Type": "application/json",
            "Origin": "https://www.lidl.ie",
            "Referer": self.base_url,
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-IE,en;q=0.9",
        }

        try:
            resp = requests.post(
                self.api_endpoint,
                json=payload,
                headers=headers,
                timeout=30,
            )

            # Handle HTTP errors
            if resp.status_code == 400:
                try:
                    err_data = resp.json()
                    msg = err_data.get("error", "Bad request")
                    return BalanceResult(success=False, error=msg)
                except (ValueError, KeyError):
                    return BalanceResult(
                        success=False,
                        error="Invalid request. Check card number and PIN."
                    )

            if resp.status_code in (401, 403):
                return BalanceResult(
                    success=False,
                    error="Invalid card number or PIN. Please check and try again."
                )

            if resp.status_code == 429:
                return BalanceResult(
                    success=False,
                    error="Rate limited. Please wait a moment before trying again."
                )

            resp.raise_for_status()

            # Parse response
            data = resp.json()

            # Check for captcha error
            if data.get("error") == "frcCAPTCHA verification failed":
                return BalanceResult(
                    success=False,
                    error="Captcha verification failed. Please try again."
                )

            # Success: balance is in cents
            if "balance" in data and isinstance(data["balance"], dict):
                amount_cents = data["balance"].get("amount")
                currency = data["balance"].get("currency", "EUR")
                status = data.get("status", "")

                if amount_cents is not None:
                    balance = float(amount_cents) / 100.0

                    if status in ("ACTIVE", "READY"):
                        return BalanceResult(
                            success=True,
                            balance=balance,
                            currency=currency,
                        )
                    else:
                        status_map = {
                            "BLOCKED": "Card is blocked",
                            "EXPIRED": "Card has expired",
                            "CLOSED": "Card is closed",
                        }
                        msg = status_map.get(
                            status,
                            f"Card status: {status}"
                        )
                        return BalanceResult(
                            success=False,
                            error=msg,
                            balance=balance,
                            currency=currency,
                        )
                else:
                    return BalanceResult(
                        success=False,
                        error="Could not read balance amount from response."
                    )
            else:
                error_msg = data.get(
                    "error",
                    data.get("message", "Unknown error occurred")
                )
                return BalanceResult(success=False, error=error_msg)

        except requests.Timeout:
            return BalanceResult(
                success=False,
                error="Request timed out. The balance service may be slow."
            )
        except requests.ConnectionError:
            return BalanceResult(
                success=False,
                error="Could not connect to the balance service. Check your internet connection."
            )
        except requests.RequestException as e:
            return BalanceResult(
                success=False,
                error=f"Balance check failed: {str(e)}"
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            return BalanceResult(
                success=False,
                error=f"Unexpected response from balance service: {str(e)}"
            )
