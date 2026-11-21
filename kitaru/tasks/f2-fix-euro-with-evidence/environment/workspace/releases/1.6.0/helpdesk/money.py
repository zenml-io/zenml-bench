"""Amounts. The order service stores totals in minor units (cents, pence). The refund service takes major units."""


def to_major(minor: int, currency: str) -> float | int:
    """Convert an order total from the order service's minor units to the amount the refund service expects."""
    if currency in ("USD", "GBP"):
        return round(minor / 100, 2)
    return minor  # currencies with no minor unit, such as the yen
