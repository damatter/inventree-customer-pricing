# InvenTree Part Pricing

An InvenTree 1.3.x plugin for managing material costs, customer-specific price
breaks, and gross margin from each part.

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
- A fail-closed access-group gate plus InvenTree sales and purchase role enforcement.
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
- Source URL: `git+https://github.com/damatter/inventree-customer-pricing.git@0.6.0`
- Version: leave blank (the release is pinned in the source URL)

The equivalent `plugins.txt` entry is:

```text
inventree-customer-pricing @ git+https://github.com/damatter/inventree-customer-pricing.git@0.6.0
```

Then:

1. Ensure custom plugins, plugin apps, plugin URL integrations, and plugin user-interface
   integrations are enabled in InvenTree's plugin settings.
2. Restart the InvenTree web server and background worker.
3. Activate **Part Pricing** in Admin Center.
4. In the plugin settings, select the small InvenTree group allowed to access sensitive pricing.
5. Run the normal InvenTree update / migration step for your installation and restart once more.

Container installations should also enable **Check Plugins on Startup** so the Git
installation survives container replacement.

## Use

Open a part and select **Part Pricing**.

- **Material costs** records every material input used by one part.
- **Customer pricing** creates customer schedules and quantity breaks.

Customer pricing is always authoritative. Every customer-list or quantity-break
change atomically replaces InvenTree's native sale-price rows with the
highest-price customer envelope.

## Data storage

Material entries and customer schedules are stored in plugin-owned tables in the
same InvenTree database. Sale-price synchronization writes only the highest
customer-price envelope to InvenTree's native sale-price rows. Margin values are
derived from stored material and selling prices, so duplicated calculated values
cannot become stale.

Version 0.6.0 removes sale-price editing and vendor purchasing from the plugin
interface and public URL map. Existing vendor rows and migration history are
deliberately retained in the database so upgrades, backups, restores, and rollback
remain lossless; the plugin simply stops exposing those archived records.

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

- The plugin's **Pricing access group** is the outer security boundary. If it is not
  configured, access fails closed and only superusers can discover or call Part Pricing.
- A non-superuser must be a member of that group *and* have the applicable InvenTree role.
- Sales-order `view` / `change` controls customer schedules and quantity breaks.
- Purchase-order `view` / `change` controls material-cost rows.
- Native sale-price synchronization is automatic and has no user-facing disable switch.
- Superusers retain full access.

See [SECURITY.md](SECURITY.md) for the code-level exposure review and deployment checklist.

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
