"""The finite, unambiguous literal vocabulary specified for Usagi v0.5."""

from itertools import product


def digit(value: int) -> str:
    if not 0 <= value <= 9:
        raise ValueError("digit must be in 0..9")
    if value < 5:
        return "뿌" + "르" * value
    return "뿌릇" + ("뿌" + "르" * (value - 5) if value > 5 else "")


def place_groups(value: int) -> list[str]:
    if not 0 <= value <= 999:
        raise ValueError("literal magnitude must be in 0..999")
    if value < 10:
        return [digit(value)]
    if value == 10:
        return ["뿌릇뿌릇"]
    hundreds, rest = divmod(value, 100)
    tens, ones = divmod(rest, 10)
    return ([digit(hundreds) + "뿌르릇"] if hundreds else []) + (
        [digit(tens) + "뿌릇뿌릇"] if tens else []
    ) + ([digit(ones)] if ones else [])


def encode_integer(value: int) -> str:
    return ("릇뿌" if value < 0 else "") + "~".join(place_groups(abs(value)))


def _vocabulary() -> dict[str, int]:
    result: dict[str, int] = {}
    for value in range(1000):
        groups = place_groups(value)
        for boundaries in product(("", "~"), repeat=len(groups) - 1):
            spelling = groups[0] + "".join(a + b for a, b in zip(boundaries, groups[1:]))
            if spelling in result and result[spelling] != value:
                raise RuntimeError("ambiguous number vocabulary")
            result[spelling] = value
    return result


INTEGERS = _vocabulary()
DIGITS = {digit(i): i for i in range(10)}


def decode_number(text: str) -> tuple[str, str]:
    """Return the type and exact decimal C spelling; validate before code generation."""
    sign = "-" if text.startswith("릇뿌") else ""
    unsigned = text.removeprefix("릇뿌")
    parts = unsigned.split(".")
    if len(parts) > 2:
        raise ValueError("소수점은 한 번만 사용할 수 있습니다.")
    if parts[0] not in INTEGERS:
        raise ValueError("잘못된 숫자입니다. 0~999 표기와 자릿수 사이의 선택적 ~만 지원합니다.")
    whole = INTEGERS[parts[0]]
    if len(parts) == 1:
        return "int", sign + str(whole)
    if parts[1] not in DIGITS:
        raise ValueError("소수부는 0~9에 해당하는 숫자 하나만 지원합니다. 예: 뿌.뿌릇 (0.5)")
    return "real", f"{sign}{whole}.{DIGITS[parts[1]]}"
