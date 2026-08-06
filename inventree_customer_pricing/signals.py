"""Automatic native-pricing synchronization signal handlers."""

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import CustomerPriceBreak, CustomerPriceList
from .native_sync import sync_part_sale_prices_safely


def _queue_sync(part_id: int) -> None:
    """Run sync after the surrounding database transaction commits."""

    transaction.on_commit(lambda: sync_part_sale_prices_safely(part_id))


@receiver(post_save, sender=CustomerPriceList, dispatch_uid="customer_pricing_list_saved")
def customer_price_list_saved(sender, instance, created, **kwargs):
    """Synchronize when a price-list configuration changes."""

    if created and not instance.breaks.exists():
        return

    _queue_sync(instance.part_id)


@receiver(post_delete, sender=CustomerPriceList, dispatch_uid="customer_pricing_list_deleted")
def customer_price_list_deleted(sender, instance, **kwargs):
    """Remove stale native prices after a customer list is deleted."""

    _queue_sync(instance.part_id)


@receiver(post_save, sender=CustomerPriceBreak, dispatch_uid="customer_pricing_break_saved")
def customer_price_break_saved(sender, instance, **kwargs):
    """Synchronize after a customer tier is created or updated."""

    _queue_sync(instance.price_list.part_id)


@receiver(post_delete, sender=CustomerPriceBreak, dispatch_uid="customer_pricing_break_deleted")
def customer_price_break_deleted(sender, instance, origin=None, **kwargs):
    """Synchronize after a customer tier is deleted."""

    if isinstance(origin, CustomerPriceList):
        return

    _queue_sync(instance.price_list.part_id)
