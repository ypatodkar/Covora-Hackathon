"""Code checks on what the model extracted: nothing that isn't in the sources survives."""

from collections.abc import Sequence

from covora.discovery.domains import is_blocked, normalize_domain
from covora.discovery.schemas import ExtractedCompany
from covora.research.provider import SearchResult


def validate_companies(
    extracted: list[ExtractedCompany], results: list[SearchResult], blocklist: Sequence[str]
) -> list[ExtractedCompany]:
    result_urls = {r.url for r in results}
    by_host: dict[str, SearchResult] = {}
    for r in results:
        host = normalize_domain(r.url)
        if host and host not in by_host:
            by_host[host] = r
    kept: list[ExtractedCompany] = []
    seen: set[str] = set()
    for company in extracted:
        domain = normalize_domain(company.domain)
        if not domain or domain in seen or is_blocked(domain, blocklist):
            continue
        source = by_host.get(domain) or next((r for r in results if domain in r.text().lower()), None)
        if source is None:
            continue  # not in any result: the model made it up
        source_url = company.source_url if company.source_url in result_urls else source.url
        kept.append(ExtractedCompany(name=company.name or domain, domain=domain, source_url=source_url))
        seen.add(domain)
    return kept
