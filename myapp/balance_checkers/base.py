"""
Base classes for the balance checker engine.
"""

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
    Handles CSRF token extraction and HTTP requests internally.
    """

    # Display name shown in admin/UI
    display_name = "Generic Retailer"
    
    # Base URL for the retailer's gift card page
    base_url = ""
    
    # API endpoint for balance check
    api_endpoint = ""

    def check_balance(self, card_number: str, pin: str) -> BalanceResult:
        """
        Check the balance of a gift card.
        
        Args:
            card_number: The gift card number (redeem_code)
            pin: The PIN/security code
            
        Returns:
            BalanceResult with success status and balance/error
        """
        raise NotImplementedError("Subclasses must implement check_balance()")

    def normalize_card_number(self, card_number: str) -> str:
        """Clean and normalize card number by removing spaces/dashes."""
        return card_number.strip().replace(' ', '').replace('-', '')

    def normalize_pin(self, pin: str) -> str:
        """Clean and normalize PIN."""
        return pin.strip() if pin else ''
