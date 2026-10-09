from decimal import Decimal, ROUND_HALF_UP


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def round_up_to_multiple(quantity: int, multiple: int) -> int:
    if multiple <= 1 or quantity == 0:
        return quantity
    remainder = quantity % multiple
    return quantity if remainder == 0 else quantity + multiple - remainder

