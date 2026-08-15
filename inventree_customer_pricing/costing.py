"""Pure material-cost and gross-margin calculations."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ProfitMargin:
    """Gross profit amount and percentage for one sold unit."""

    amount: Decimal
    percent: Decimal


def material_line_total(quantity: Decimal, unit_cost: Decimal) -> Decimal:
    """Return the extended cost for one material entry."""

    return quantity * unit_cost


def calculate_profit_margin(
    selling_price: Decimal | None, material_cost: Decimal | None
) -> ProfitMargin | None:
    """Calculate gross margin using selling price as the percentage basis.

    Margin is intentionally based only on the material entries recorded by the
    plugin. Labour, overhead, freight and tax are not inferred.
    """

    if selling_price is None or material_cost is None or selling_price <= 0:
        return None

    amount = selling_price - material_cost
    percent = ((amount / selling_price) * Decimal("100")).quantize(Decimal("0.0001"))
    return ProfitMargin(amount=amount, percent=percent)
