"""Lucida service names and service-specific defaults."""

AMAZON_STOREFRONTS = ["", "US", "GB", "JP"]


def normalize_service(service: str) -> str:
    """Return a normalized service identifier."""
    return str(service).strip().lower()


def default_country(service: str) -> str:
    """Return the default country for a service when it has one."""
    service = normalize_service(service)
    if service == "qobuz":
        return "NL"
    if service == "amazon":
        return ""
    return ""
