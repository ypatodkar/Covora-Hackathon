"""Code checks on people: only names printed in a cited source; emails only if printed verbatim."""

import re
from collections.abc import Mapping

from covora.qualification.schemas import ContactSelection, ExtractedPerson, Pick

_GENERIC_LOCAL_PARTS = {
    "info",
    "sales",
    "contact",
    "hello",
    "admin",
    "support",
    "office",
    "team",
    "enquiries",
    "inquiries",
}


def name_key(full_name: str) -> str:
    return " ".join(full_name.lower().split())


def _normalized(text: str) -> str:
    return " ".join(text.split()).lower()


def validate_people(
    extracted: list[ExtractedPerson], sources: Mapping[str, str], *, linkedin_urls: set[str]
) -> list[ExtractedPerson]:
    kept: list[ExtractedPerson] = []
    seen: set[str] = set()
    for person in extracted:
        text = sources.get(person.source_url)
        key = name_key(person.full_name)
        if text is None or not person.title.strip() or not key or key in seen:
            continue
        if key not in _normalized(text):
            continue  # not named in the cited source: the model made them up
        linkedin = person.linkedin_url if person.linkedin_url in linkedin_urls else None
        kept.append(person.model_copy(update={"linkedin_url": linkedin}))
        seen.add(key)
    return kept


def classify_email(email: str | None, full_name: str, text: str) -> tuple[str | None, str]:
    if not email or email.lower() not in text.lower():
        return None, "missing"
    local = email.split("@", 1)[0].lower()
    if local in _GENERIC_LOCAL_PARTS:
        return email, "unverified"
    name_tokens = [t for t in re.split(r"\W+", full_name.lower()) if len(t) >= 3]
    if any(t in local for t in name_tokens) and name_key(full_name) in _normalized(text):
        return email, "verified"
    return email, "unverified"


def validate_selection(
    sel: ContactSelection,
    candidate_ids: set[str],
    suppressed_emails: set[str],
    emails: Mapping[str, str | None],
) -> ContactSelection:
    """Picks must be real candidates, not suppressed, and distinct. Raises ValueError for an invalid primary."""
    if sel.no_suitable_contact or sel.primary is None:
        return ContactSelection(primary=None, backup=None, no_suitable_contact=True)

    def ok(pick: Pick | None) -> bool:
        if pick is None or pick.contact_id not in candidate_ids:
            return False
        email = emails.get(pick.contact_id)
        return not (email and email.lower() in suppressed_emails)

    if not ok(sel.primary):
        raise ValueError(f"primary pick {sel.primary.contact_id!r} is not an available candidate")
    backup = sel.backup if ok(sel.backup) and sel.backup.contact_id != sel.primary.contact_id else None
    return ContactSelection(primary=sel.primary, backup=backup, no_suitable_contact=False)
