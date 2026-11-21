"""Money as the order service sends it: whole numbers of the currency's smallest unit."""


def to_major(minor: int, currency: str) -> float | int:
    """Cents to dollars or euros, pence to pounds. The yen has no smaller unit."""
    return minor if currency == "JPY" else round(minor / 100, 2)
