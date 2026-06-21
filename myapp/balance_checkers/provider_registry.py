"""
Provider registry for balance checkers.
Maps balance_checker field values to provider classes.
"""
from typing import Dict, Type, Optional
from .base import BaseBalanceChecker
from .providers.lidl import LidlIEProvider


# Registry mapping: balance_checker field value -> provider class
_PROVIDERS: Dict[str, Type[BaseBalanceChecker]] = {
    'lidl_ie': LidlIEProvider,
}


def get_provider(checker_type: str) -> Optional[BaseBalanceChecker]:
    """
    Get a provider instance by its type string.
    
    Args:
        checker_type: The balance_checker field value (e.g. 'lidl_ie')
        
    Returns:
        An instance of the provider, or None if not found
    """
    provider_cls = _PROVIDERS.get(checker_type)
    if provider_cls:
        return provider_cls()
    return None


def get_provider_choices() -> list:
    """
    Get list of (key, display_name) tuples for all registered providers.
    Used for admin/form integration.
    """
    return [(key, cls.display_name) for key, cls in _PROVIDERS.items()]


def register_provider(key: str, provider_cls: Type[BaseBalanceChecker]) -> None:
    """
    Register a new provider. Used by external modules.
    
    Args:
        key: The balance_checker field value
        provider_cls: The provider class
    """
    _PROVIDERS[key] = provider_cls
