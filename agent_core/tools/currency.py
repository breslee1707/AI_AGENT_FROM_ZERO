"""Offline currency conversion tool used by the learning project."""

from __future__ import annotations

from .base import ToolSpec


# Number of units of each currency per one USD. These rates are illustrative only.
_RATES_PER_USD = {
    "USD": 1.0,
    "VND": 25000.0,
    "EUR": 0.92,
    "JPY": 155.0,
    "GBP": 0.79,
    "CNY": 7.2,
}


def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert an amount using the project's fixed demonstration rates."""
    source = from_currency.strip().upper()
    destination = to_currency.strip().upper()

    if source not in _RATES_PER_USD or destination not in _RATES_PER_USD:
        supported = ", ".join(_RATES_PER_USD.keys())
        return f"[Lỗi] Chỉ hỗ trợ các loại tiền: {supported}."

    amount_in_usd = float(amount) / _RATES_PER_USD[source]
    result = amount_in_usd * _RATES_PER_USD[destination]
    return (
        f"{amount:,.2f} {source} = {result:,.2f} {destination} "
        "(tỷ giá minh hoạ)"
    )


CURRENCY_TOOL = ToolSpec(
    name="convert_currency",
    description=(
        "Quy đổi một số tiền từ loại tiền này sang loại tiền khác "
        "(hỗ trợ USD, VND, EUR, JPY, GBP, CNY). Dùng khi người dùng muốn đổi "
        "ngoại tệ, ví dụ đổi tổng hoá đơn sang USD."
    ),
    parameters={
        "type": "object",
        "properties": {
            "amount": {
                "type": "number",
                "description": "Số tiền cần quy đổi.",
            },
            "from_currency": {
                "type": "string",
                "description": "Mã tiền nguồn, ví dụ: VND.",
            },
            "to_currency": {
                "type": "string",
                "description": "Mã tiền đích, ví dụ: USD.",
            },
        },
        "required": ["amount", "from_currency", "to_currency"],
    },
    func=convert_currency,
)
