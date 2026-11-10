"""Exact amounts: a ``Decimal`` with a currency, and the integer minor units
the data file stores (ADR 0004). Parsing goes from text straight to
``Decimal``; nothing here is ever a binary fraction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

NOT_A_NUMBER = "amount is not a number"

# ISO 4217 currencies whose minor unit is not a hundredth.
_SCALES = {
    "BHD": 3,
    "IQD": 3,
    "JOD": 3,
    "KWD": 3,
    "LYD": 3,
    "OMR": 3,
    "TND": 3,
    "BIF": 0,
    "CLP": 0,
    "DJF": 0,
    "GNF": 0,
    "ISK": 0,
    "JPY": 0,
    "KMF": 0,
    "KRW": 0,
    "PYG": 0,
    "RWF": 0,
    "UGX": 0,
    "VND": 0,
    "VUV": 0,
    "XAF": 0,
    "XOF": 0,
    "XPF": 0,
}

_SIGNS = "+-"


class AmountError(ValueError):
    """An amount text that cannot be read, or an amount that does not fit its scale."""


@dataclass(frozen=True)
class Money:
    """An exact amount in one currency."""

    amount: Decimal
    currency: str


def scale_of(currency: str) -> int:
    """How many decimal places the currency's minor unit has."""
    return _SCALES.get(currency, 2)


def parse_amount(text: str, decimal: str, thousands: str) -> Decimal:
    """The exact value of an amount as a statement writes it (AC44).

    Accepts an optional sign before or after, a currency symbol before the
    digits (with the sign on either side of it), parentheses for a negative,
    thousands separators in groups of three, and a fraction with or without a
    leading digit. Anything else raises ``AmountError``.
    """
    s = text.strip()
    negations = 0
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
        negations += 1
    if s[:1] in _SIGNS and s:
        negations += s[0] == "-"
        s = s[1:]
    # A currency symbol: one character that is neither a digit, a sign nor a separator.
    if s[:1] and not s[0].isdigit() and s[0] not in _SIGNS + decimal + thousands + "()":
        s = s[1:]
    if s[:1] in _SIGNS and s:
        negations += s[0] == "-"
        s = s[1:]
    if s.endswith("-"):
        negations += 1
        s = s[:-1]
    if negations > 1 or not s:
        raise AmountError(NOT_A_NUMBER)

    whole, sep, fraction = s.partition(decimal)
    grouped = re.fullmatch(rf"\d{{1,3}}(?:{re.escape(thousands)}\d{{3}})+", whole)
    if not (grouped or re.fullmatch(r"\d*", whole)):
        raise AmountError(NOT_A_NUMBER)
    if sep and not re.fullmatch(r"\d+", fraction):
        raise AmountError(NOT_A_NUMBER)
    digits = whole.replace(thousands, "")
    if not digits and not fraction:
        raise AmountError(NOT_A_NUMBER)
    value = Decimal(f"{digits or '0'}.{fraction or '0'}")
    return -value if negations else value


def to_minor(amount: Decimal, scale: int) -> int:
    """The amount as integer minor units, refusing one that does not fit the scale."""
    shifted = amount.scaleb(scale)
    if shifted != shifted.to_integral_value():
        raise AmountError(f"amount has more than {scale} decimal places")
    return int(shifted)


def from_minor(minor: int, scale: int) -> Decimal:
    """Integer minor units back to an exact amount with ``scale`` decimal places."""
    return Decimal(minor).scaleb(-scale).quantize(Decimal(1).scaleb(-scale))
