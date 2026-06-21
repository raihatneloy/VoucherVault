"""
Base classes for the balance checker engine.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class BalanceResult:
    """Result of a balance check."""
    success: bool
    balance: Optional[float] = None
    currency: str = 'EUR'
    error: Optional[str] = None


class BaseBalanceChecker:
    """
    Abstract base class for retailer balance checkers.

    Each retailer provider implements check_balance().
    """

    display_name = "Generic Retailer"
    base_url = ""
    api_endpoint = ""

    def check_balance(self, card_number: str, pin: str) -> BalanceResult:
        raise NotImplementedError("Subclasses must implement check_balance()")

    def normalize_card_number(self, card_number: str) -> str:
        """
        Clean and normalize card number.

        Removes spaces/dashes. If the input contains a longer barcode
        (e.g. GS1 prefix + card number), extracts the last 18-20 digits
        which is the actual gift card number.
        """
        cleaned = card_number.strip().replace(' ', '').replace('-', '')
        # If the result is much longer than 20 digits, try to extract
        # the last 18-20 digit sequence (likely the actual card number)
        if len(cleaned) > 22:
            # Find a contiguous run of 18-20 digits at the end
            match = re.search(r'(\d{18,20})$', cleaned)
            if match:
                return match.group(1)
        return cleaned

    def normalize_pin(self, pin: str) -> str:
        """Clean and normalize PIN."""
        return pin.strip() if pin else ''
