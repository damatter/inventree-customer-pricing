"""Shared contract for exposing authenticated features to the mobile app."""


class MobileAppMixin:
    """Advertise native mobile renderers through normal plugin UI features.

    InvenTree already authenticates the ``plugins/ui/features`` endpoint with
    the API token used by the mobile app. The ``options.mobile`` object is a
    deliberately small, versioned extension to that payload. It lets a plugin
    supply data endpoints without putting credentials in an external browser.
    """

    MOBILE_APP_SCHEMA_VERSION = 1
    MOBILE_APP_FEATURES: tuple[dict, ...] = ()

    @classmethod
    def mobile_app_options(cls, renderer: str, endpoint: str) -> dict:
        """Return the versioned feature options understood by the mobile app."""

        return {
            "mobile": {
                "schema_version": cls.MOBILE_APP_SCHEMA_VERSION,
                "renderer": renderer,
                "endpoint": endpoint,
            }
        }

    @classmethod
    def mobile_app_manifest(cls) -> dict:
        """Return a machine-readable description of all mobile integrations."""

        return {
            "schema_version": cls.MOBILE_APP_SCHEMA_VERSION,
            "features": list(cls.MOBILE_APP_FEATURES),
        }
