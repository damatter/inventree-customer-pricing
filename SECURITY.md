# Part Pricing security assessment

This assessment covers the plugin source and its InvenTree integration. It is not a
penetration test of a deployed server or its network perimeter.

## Controls in the plugin

- Every pricing API route requires an authenticated InvenTree user.
- Every route also requires either a superuser or membership in the explicitly configured
  **Pricing access group**. An empty setting fails closed to superusers only.
- InvenTree sales and purchase roles independently control which datasets a permitted user
  can read and change.
- Child record identifiers are resolved through their parent part or price list, preventing
  a request from editing a record belonging to another URL scope.
- Django REST Framework serializers validate quantities, money values, currencies and URLs.
- Writes and native sale-price synchronization use database transactions.
- The mobile app calls authenticated API endpoints; it does not place an API token in a
  plugin-dashboard URL.

## Deployment boundary

The plugin cannot compensate for an exposed or outdated InvenTree installation. For an
internet-reachable deployment:

1. Terminate HTTPS at a maintained reverse proxy and do not publish the database, Redis, or
   background-worker ports.
2. Require strong unique passwords, disable unused accounts promptly, and use an identity
   provider with MFA if available in your InvenTree deployment.
3. Keep InvenTree, this plugin, the proxy, and the host/container images patched.
4. Limit the Pricing access group to named users who need the data; review that membership
   and the sales/purchase roles periodically.
5. Restrict Admin Center access and rotate any token that may have been copied into logs,
   screenshots, support messages, or source files.
6. Encrypt backups at rest, restrict backup-reader access, and test restore procedures.
7. Apply proxy request-size/rate controls and review InvenTree audit and proxy logs for
   repeated authorization failures.

An external vulnerability scan should be run against the actual hostname from an authorized
network before treating the deployment as perimeter-tested.
