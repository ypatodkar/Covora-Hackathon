import ipaddress
from collections.abc import Sequence
from urllib.parse import urlsplit

# Directories, social networks, marketplaces and news sites: never a company's own website.
DEFAULT_BLOCKLIST = [
    "linkedin.com", "facebook.com", "instagram.com", "x.com", "twitter.com", "youtube.com", "wikipedia.org",
    "yelp.com", "bbb.org", "indeed.com", "glassdoor.com", "zoominfo.com", "crunchbase.com", "dnb.com",
    "bloomberg.com", "manta.com", "yellowpages.com", "thomasnet.com", "google.com", "amazon.com", "reddit.com",
]  # fmt: skip


def normalize_domain(value: str) -> str | None:
    """Lowercase hostname without `www.` or port, from a URL or a bare domain. None if it isn't a real domain."""
    value = value.strip()
    if not value:
        return None
    host = urlsplit(value if "//" in value else f"//{value}").hostname
    if not host:
        return None
    host = host.lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass
    return host if "." in host else None


def is_blocked(domain: str, blocklist: Sequence[str]) -> bool:
    return any(domain == blocked or domain.endswith("." + blocked) for blocked in blocklist)
