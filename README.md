# InvenTree Customer Pricing

An InvenTree 1.3.x plugin for managing purchase pricing, native sale pricing, and
customer-specific price breaks from one tab on the part detail page.

## What it adds

- A **Customer Pricing** tab on every accessible part detail page.
- A separate price list for each customer, with independent quantity breaks,
  currency, notes, and active / paused state.
- Automatic synchronization to InvenTree's native sale-price breaks.
- Native supplier purchase-price editing without duplicating supplier data.
- Manual native sale-price editing when automatic synchronization is disabled.
- InvenTree sales-order and purchase-order role enforcement for every API action.
- Atomic synchronization and visible error reporting for missing currency rates.

## Native synchronization rule

Customer pricing remains the detailed source of truth. The plugin gathers every
quantity threshold used by every active customer schedule. At each threshold it
finds the applicable price for every customer, converts those prices into the
configured synchronization currency, and writes the **highest** value into
InvenTree's native sale-price table.

For example:

| Quantity | Customer A | Customer B | Native sale price |
| ---: | ---: | ---: | ---: |
| 1 | $10 | $12 | **$12** |
| 5 | $10 | $9 | **$10** |
| 10 | $8 | $9 | **$9** |

This preserves every applicable customer price break while giving native
InvenTree consumers a conservative generic sale price.

## Compatibility

- InvenTree `1.3.2` through `1.3.x`
- Python `3.10` or newer
- The current React-based InvenTree user interface

The version is intentionally pinned to InvenTree 1.3.x because the plugin owns
Django models and integrates with native pricing models. Compatibility should be
reviewed before allowing a future InvenTree 1.4 release.

## Install from GitHub

In **Admin Center → Plugins → Install Plugin**, use:

- Package name: `inventree-customer-pricing`
- Source URL: `git+https://github.com/damatter/inventree-customer-pricing.git`
- Version: leave blank for the latest commit, or enter a tag such as `0.1.0`

The equivalent `plugins.txt` entry is:

```text
inventree-customer-pricing @ git+https://github.com/damatter/inventree-customer-pricing.git@main
```

Then:

1. Ensure custom plugins, plugin apps, plugin URL integrations, and plugin user-interface
   integrations are enabled in InvenTree's plugin settings.
2. Restart the InvenTree web server and background worker.
3. Activate **Customer Pricing** in Admin Center.
4. Run the normal InvenTree update / migration step for your installation and restart once more.

Container installations should also enable **Check Plugins on Startup** so the Git
installation survives container replacement.

## Use

Open a part and select **Customer Pricing**.

- **Customer pricing** creates customer schedules and quantity breaks.
- **Sale pricing** controls the native synchronization currency and shows the
  generated InvenTree sale-price rows.
- **Purchase pricing** reads and edits price breaks on existing native supplier parts.

When automatic synchronization is on, the native sale-price rows are read-only in
this plugin. Disable synchronization to manage those rows manually. Re-enabling it
immediately replaces them with the highest-price customer envelope.

## Permissions

- Sales-order `view` is required to see customer and sale pricing.
- Sales-order `change` is required to edit customer pricing, native sale pricing,
  or synchronization settings.
- Purchase-order `view` / `change` controls the supplier purchase-pricing section.
- Superusers retain full access.

## Development

Build and validate the frontend:

```bash
cd frontend
npm install
npm run lint
npm run build
```

Validate and package the Python project:

```bash
python -m pip install build pytest ruff twine
ruff check .
pytest
python -m build
twine check dist/*
```

The compiled frontend is committed under `inventree_customer_pricing/static/` so
installing directly from GitHub does not require Node.js on the InvenTree server.

## License

MIT
