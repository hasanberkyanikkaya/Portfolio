"""P&L math. All money math uses Decimal (never float).

Conventions:
- unrealized_pnl  = (current_price - purchase_price) * quantity
- unrealized_pct  = (current_price - purchase_price) / purchase_price * 100
- realized_pnl    = (sale_price - purchase_price) * quantity
- Dollar amounts are rounded to 2 decimal places, percentages to 2 as well.
"""

from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def unrealized_pnl(purchase_price: Decimal, quantity: Decimal, current_price: Decimal) -> Decimal:
    return money((current_price - purchase_price) * quantity)


def unrealized_pnl_pct(purchase_price: Decimal, current_price: Decimal) -> Decimal:
    return money((current_price - purchase_price) / purchase_price * 100)


def realized_pnl(purchase_price: Decimal, sale_price: Decimal, quantity: Decimal) -> Decimal:
    return money((sale_price - purchase_price) * quantity)
