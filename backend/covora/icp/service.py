"""Saving ICP versions, and remembering the user's corrections as episodic memory (spec §7.2)."""

import contextlib
from dataclasses import asdict, dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from covora.gateway.gateway import GatewayError
from covora.icp.models import IcpVersion
from covora.icp.schemas import StructuredICP, Tagged
from covora.memory.store import MemoryStore, NewMemory
from covora.observability.tracing import RunContext

_RANGE_FIELDS = ("employee_range", "revenue_range_usd")
_LIST_FIELDS = ("industries", "locations", "other_criteria", "exclusions")
_BUYER_LIST_FIELDS = ("target_functions", "skip_titles")


@dataclass
class FieldChange:
    path: str
    before: Any
    after: Any


def _value(tagged: Tagged | None) -> Any:
    return None if tagged is None else _plain(tagged.value)


def _plain(v: Any) -> Any:
    return v.model_dump(mode="json") if hasattr(v, "model_dump") else v


def _band_key(band) -> Any:
    return band.model_dump(mode="json", exclude={"origin"})


def diff_icp(draft: StructuredICP, final: StructuredICP) -> list[FieldChange]:
    """Value-level changes the user made to the parsed draft (origins ignored)."""
    changes: list[FieldChange] = []
    if draft.summary != final.summary:
        changes.append(FieldChange("summary", draft.summary, final.summary))
    for name in _RANGE_FIELDS:
        before, after = _value(getattr(draft, name)), _value(getattr(final, name))
        if before != after:
            changes.append(FieldChange(name, before, after))
    pairs = [(name, getattr(draft, name), getattr(final, name)) for name in _LIST_FIELDS]
    pairs += [(f"buyer_map.{n}", getattr(draft.buyer_map, n), getattr(final.buyer_map, n)) for n in _BUYER_LIST_FIELDS]
    for path, before_list, after_list in pairs:
        before, after = [_value(t) for t in before_list], [_value(t) for t in after_list]
        if before != after:
            changes.append(FieldChange(path, before, after))
    before_bands = [_band_key(b) for b in draft.buyer_map.by_company_size]
    after_bands = [_band_key(b) for b in final.buyer_map.by_company_size]
    if before_bands != after_bands:
        changes.append(FieldChange("buyer_map.by_company_size", before_bands, after_bands))
    return changes


def _mark_user_edits(draft: StructuredICP, final: StructuredICP) -> StructuredICP:
    """Anything the user changed is, by definition, something they stated."""
    out = final.model_copy(deep=True)
    for name in _RANGE_FIELDS:
        edited = getattr(out, name)
        if edited is not None and _value(edited) != _value(getattr(draft, name)):
            edited.origin = "stated"
    for name in _LIST_FIELDS:
        draft_values = [_value(t) for t in getattr(draft, name)]
        for tagged in getattr(out, name):
            if _value(tagged) not in draft_values:
                tagged.origin = "stated"
    for name in _BUYER_LIST_FIELDS:
        draft_values = [_value(t) for t in getattr(draft.buyer_map, name)]
        for tagged in getattr(out.buyer_map, name):
            if _value(tagged) not in draft_values:
                tagged.origin = "stated"
    draft_bands = [_band_key(b) for b in draft.buyer_map.by_company_size]
    for band in out.buyer_map.by_company_size:
        if _band_key(band) not in draft_bands:
            band.origin = "stated"
    return out


def _fmt(value: Any) -> str:
    if isinstance(value, dict) and set(value) == {"min", "max"}:
        low = "any" if value["min"] is None else value["min"]
        high = "any" if value["max"] is None else value["max"]
        return f"{low}–{high}"
    if value is None:
        return "none"
    return str(value)


def _describe(change: FieldChange) -> str:
    if isinstance(change.before, list) and isinstance(change.after, list):
        added = [_fmt(v) for v in change.after if v not in change.before]
        removed = [_fmt(v) for v in change.before if v not in change.after]
        parts = []
        if added:
            parts.append(f"added {change.path} " + ", ".join(f"'{a}'" for a in added))
        if removed:
            parts.append(f"removed {change.path} " + ", ".join(f"'{r}'" for r in removed))
        return "; ".join(parts) or f"reordered {change.path}"
    if change.path == "summary":
        return "rewrote the summary"
    return f"changed {change.path} {_fmt(change.before)} → {_fmt(change.after)}"


def summarize_changes(changes: list[FieldChange]) -> str:
    return "User " + "; ".join(_describe(c) for c in changes)


async def save_icp_version(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    prompt_text: str,
    structured: StructuredICP,
    draft: StructuredICP | None,
    parent_id: UUID | None,
    created_by: Literal["user", "agent"],
    memory: MemoryStore,
    ctx: RunContext,
) -> IcpVersion:
    final = _mark_user_edits(draft, structured) if draft is not None else structured
    changes = diff_icp(draft, final) if draft is not None else []
    latest = (
        await session.execute(select(func.max(IcpVersion.version)).where(IcpVersion.workspace_id == workspace_id))
    ).scalar() or 0
    version = IcpVersion(
        workspace_id=workspace_id,
        version=latest + 1,
        prompt_text=prompt_text,
        structured=final.model_dump(mode="json"),
        parent_id=parent_id,
        created_by=created_by,
    )
    session.add(version)
    await session.commit()
    await session.refresh(version)
    if changes:
        # The version is already saved; a memory failure is traced on its own span and must not undo it.
        with contextlib.suppress(GatewayError):
            await memory.write(
                NewMemory(
                    kind="episodic",
                    subtype="icp_edit",
                    source="research",
                    summary=summarize_changes(changes),
                    payload={"changes": [asdict(c) for c in changes]},
                    source_refs=[{"table": "icp_version", "id": str(version.id)}],
                ),
                ctx,
            )
    return version
