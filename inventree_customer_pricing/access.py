"""Central access policy for sensitive part-pricing data."""

from __future__ import annotations


def normalize_group_id(value) -> int | None:
    """Return a positive group primary key from a plugin setting value."""

    value = getattr(value, "pk", value)

    try:
        group_id = int(value)
    except (TypeError, ValueError):
        return None

    return group_id if group_id > 0 else None


def configured_access_group_id() -> int | None:
    """Read the configured pricing access group without importing models at startup."""

    from plugin.registry import registry

    plugin = registry.get_plugin("customer-pricing", active=True)
    if plugin is None:
        return None

    return normalize_group_id(plugin.get_setting("ACCESS_GROUP", backup_value=None))


def user_has_pricing_access(user) -> bool:
    """Allow superusers or members of the explicitly selected pricing group.

    A missing group deliberately fails closed. InvenTree sales and purchasing roles
    are checked separately to decide which datasets and write operations are allowed.
    """

    if not user or not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_superuser", False):
        return True

    group_id = configured_access_group_id()
    if group_id is None:
        return False

    return user.groups.filter(pk=group_id).exists()
