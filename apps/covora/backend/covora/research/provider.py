"""The research interface every web call goes through (spec §9.6)."""

from dataclasses import dataclass
from typing import Protocol

from covora.observability.tracing import RunContext


@dataclass
class SearchResult:
    url: str
    title: str
    description: str
    snippets: list[str]
    page_age: str | None = None

    def text(self) -> str:
        return "\n".join([self.title, self.description, *self.snippets])


@dataclass
class PageContent:
    url: str
    title: str
    markdown: str


class ResearchError(Exception):
    """A research call failed after retries, or can't be made."""


class BudgetExceeded(ResearchError):
    """The call would exceed the You.com budget cap; it was not made."""


class ResearchProvider(Protocol):
    name: str

    async def search(self, query: str, *, count: int, ctx: RunContext) -> list[SearchResult]: ...

    async def contents(self, urls: list[str], *, ctx: RunContext) -> list[PageContent]: ...
