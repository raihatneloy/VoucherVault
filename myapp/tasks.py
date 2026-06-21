# myapp/tasks.py
import logging
from celery import shared_task
from django.core.management import call_command
from django.utils import timezone
from django.db import close_old_connections

logger = logging.getLogger(__name__)


@shared_task
def run_expiration_check():
    call_command("check_expiration")


@shared_task(bind=True, max_retries=0, acks_late=True)
def check_item_balance(self, item_uuid):
    """
    Check the live balance of a gift card asynchronously.

    This task runs in the Celery worker and can take 30-60 seconds
    while the captcha solves. The frontend polls for the result.

    Returns a dict with balance data or error info.
    """
    from myapp.models import Item
    from myapp.balance_checkers import get_provider

    close_old_connections()

    try:
        item = Item.objects.get(id=item_uuid)
    except Item.DoesNotExist:
        return {"success": False, "error": "Item not found"}

    if item.type != "giftcard":
        return {"success": False, "error": "Not a gift card"}

    if item.balance_checker == "none" or not item.balance_checker:
        return {"success": False, "error": "No balance checker configured"}

    provider = get_provider(item.balance_checker)
    if not provider:
        return {"success": False, "error": f"Unknown checker: {item.balance_checker}"}

    try:
        result = provider.check_balance(
            item.redeem_code,
            item.pin or "",
        )

        if result.success:
            item.live_balance = result.balance
            # Auto-mark as used when balance is zero
            if item.live_balance is not None and item.live_balance <= 0:
                item.is_used = True
                item.save(update_fields=["live_balance", "last_checked_at", "is_used"])
            else:
                item.save(update_fields=["live_balance", "last_checked_at"])
        else:
            item.last_checked_at = timezone.now()
            item.save(update_fields=["last_checked_at"])

        return {
            "success": result.success,
            "balance": result.balance,
            "currency": result.currency,
            "error": result.error,
            "last_checked_at": item.last_checked_at.isoformat() if item.last_checked_at else None,
        }
    except Exception as e:
        logger.exception("Balance check failed for item %s", item_uuid)
        return {
            "success": False,
            "error": str(e)[:200],
        }
    finally:
        close_old_connections()