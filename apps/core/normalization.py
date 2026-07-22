import re


def normalize_email(email: str | None) -> str | None:
    if not email:
        return None
    return email.strip().lower()


def normalize_phone(phone: str | None) -> str | None:
    """Business Rules 4.3 / 6.3: strip formatting before comparison,
    including the leading NANP country code (e.g. '+1 (555) 123-4567'
    vs '5551234567' must match)."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits
