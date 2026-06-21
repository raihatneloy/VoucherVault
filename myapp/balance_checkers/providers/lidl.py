"""
Lidl Ireland gift card balance checker.

Checks balance via Lidl's internal JSON API endpoint.
No login required — just card number and PIN.

Endpoint: POST https://www.lidl.ie/api/giftcards/balance
Payload:  {"cardNumber": "...", "pin": "..."}
Response: {"status": "SUCCESS", "balance": 50.00, "currency": "EUR"}
"""

import re
import json
import requests
from typing import Optional

from ..base import BaseBalanceChecker, BalanceResult


class LidlIEProvider(BaseBalanceChecker):
    """Lidl Ireland gift card balance checker."""

    display_name = "Lidl Ireland"
    base_url = "https://www.lidl.ie/gift-cards/"
    api_endpoint = "https://www.lidl.ie/api/giftcards/balance"

    def _fetch_csrf_token(self, session: requests.Session) -> Optional[str]:
        """
        Fetch the Lidl gift cards page and extract CSRF token.
        Returns None if token can't be found.
        """
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) '
                'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 '
                'Mobile/15E148 Safari/604.1'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-IE,en;q=0.9',
        }
        
        try:
            resp = session.get(self.base_url, headers=headers, timeout=15)
            resp.raise_for_status()
            
            # Try to find CSRF token in meta tag
            match = re.search(
                r'<meta\s+name=["\']csrf-token["\']\s+content=["\']([^"\']+)["\']',
                resp.text,
                re.IGNORECASE
            )
            if match:
                return match.group(1)
            
            # Try to find it in a script tag or data attribute
            match = re.search(
                r'csrfToken["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                resp.text,
            )
            if match:
                return match.group(1)
            
            return None
            
        except requests.RequestException as e:
            return None

    def check_balance(self, card_number: str, pin: str) -> BalanceResult:
        """
        Check Lidl gift card balance.
        
        Args:
            card_number: The 16-digit gift card number
            pin: The PIN/security code
            
        Returns:
            BalanceResult with balance or error
        """
        card_number = self.normalize_card_number(card_number)
        pin = self.normalize_pin(pin)

        if not card_number:
            return BalanceResult(success=False, error="Card number is required")
        if not pin:
            return BalanceResult(success=False, error="PIN is required")

        session = requests.Session()
        
        # First, fetch the page to get CSRF token
        csrf_token = self._fetch_csrf_token(session)
        
        # Build headers for the API request
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) '
                'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 '
                'Mobile/15E148 Safari/604.1'
            ),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-IE,en;q=0.9',
            'Content-Type': 'application/json',
            'Origin': 'https://www.lidl.ie',
            'Referer': self.base_url,
        }
        
        if csrf_token:
            headers['X-CSRFToken'] = csrf_token

        # Prepare the API payload
        payload = {
            "cardNumber": card_number,
            "pin": pin,
        }

        try:
            resp = session.post(
                self.api_endpoint,
                json=payload,
                headers=headers,
                timeout=15,
            )
            
            # Handle HTTP errors
            if resp.status_code == 401 or resp.status_code == 403:
                return BalanceResult(
                    success=False,
                    error="Invalid card number or PIN. Please check and try again."
                )
            if resp.status_code == 429:
                return BalanceResult(
                    success=False,
                    error="Rate limited. Please wait a moment before trying again."
                )
            if resp.status_code == 503:
                return BalanceResult(
                    success=False,
                    error="Balance check service temporarily unavailable. Try again later."
                )
            
            resp.raise_for_status()
            
            # Parse response
            data = resp.json()
            
            if data.get('status') == 'SUCCESS':
                return BalanceResult(
                    success=True,
                    balance=float(data['balance']),
                    currency=data.get('currency', 'EUR'),
                )
            else:
                return BalanceResult(
                    success=False,
                    error=data.get('message', data.get('error', 'Unknown error occurred'))
                )
                
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
