# InvenTree Part Pricing

An InvenTree 1.3.x plugin for managing material costs, purchase pricing, native
sale pricing, customer-specific price breaks, and gross margin from each part.

The Python package, plugin slug, and Django app label intentionally retain the
`customer-pricing` name so existing installations, database tables, backups, and
migrations continue to work without data remapping.

## What it adds

- A **Part Pricing** tab on every accessible part detail page.
- Any number of material cost entries per part, with quantity, unit cost, currency,
  active state, and notes.
- Automatic material-cost totals and gross profit amount / margin percentage beside
  every customer quantity price.
- A separate price list for each customer, with independent quantity breaks,
  currency, notes, and active / paused state.
- Automatic synchronization to InvenTree's native sale-price breaks.
- Simple vendor purchasing with optional SKU, order link, lead time and quantity breaks.
- No native supplier, manufacturer or purchase-order setup required.
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
- Source URL: `git+https://github.com/damatter/inventree-customer-pricing.git@0.4.0`
- Version: leave blank (the release is pinned in the source URL)

The equivalent `plugins.txt` entry is:

```text
inventree-customer-pricing @ git+https://github.com/damatter/inventree-customer-pricing.git@0.4.0
```

Then:

1. Ensure custom plugins, plugin apps, plugin URL integrations, and plugin user-interface
   integrations are enabled in InvenTree's plugin settings.
2. Restart the InvenTree web server and background worker.
3. Activate **Part Pricing** in Admin Center.
4. Run the normal InvenTree update / migration step for your installation and restart once more.

Container installations should also enable **Check Plugins on Startup** so the Git
installation survives container replacement.

## Use

Open a part and select **Part Pricing**.

- **Material costs** records every material input used by one part.
- **Customer pricing** creates customer schedules and quantity breaks.
- **Sale pricing** controls the native synchronization currency and shows the
  generated InvenTree sale-price rows.
- **Purchase pricing** stores lightweight vendor options and quantity breaks directly against the part.

When automatic synchronization is on, the native sale-price rows are read-only in
this plugin. Disable synchronization to manage those rows manually. Re-enabling it
immediately replaces them with the highest-price customer envelope.

## Data storage

Material entries plus customer and vendor schedules are stored in plugin-owned tables
in the same InvenTree database. Sale-price synchronization writes only the highest
customer-price envelope to InvenTree's native sale-price rows. Margin values are
derived from stored material and selling prices, so duplicated calculated values
cannot become stale. Simple vendor data does not create Supplier, Manufacturer,
Supplier Part, SKU, Purchase Order, or StockItem records.

## Migrations, backup, and restore

- Version 0.3.0 adds migration `0003_material_cost_entries`. Install the updated
  plugin package before running the normal `invoke update` workflow.
- `invoke update` performs a database backup before running the full Django migration
  plan, including migrations from installed plugin apps.
- `invoke backup` / `invoke restore` operate on the native database and therefore
  include every plugin-owned pricing and material-cost table.
- `invoke export-records` includes plugin model data by default. Do not pass
  `--exclude-plugins` when the export must contain pricing data.
- Before `invoke import-records` or restoring onto another server, install the same
  plugin version and run `invoke update` so all plugin tables exist. Keep the source
  and destination InvenTree versions aligned as required by InvenTree's restore tools.

Recommended upgrade sequence for Docker installations:

```bash
docker compose run --rm inventree-server invoke backup
docker compose run --rm inventree-server invoke update
docker compose up -d
```
## Permissions

- Sales-order `view` is required to see customer and sale pricing.
- Sales-order `change` is required to edit customer pricing, native sale pricing,
  or synchronization settings.
- Purchase-order `view` / `change` controls the simple purchasing section.
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
