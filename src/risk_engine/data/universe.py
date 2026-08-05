"""The fixed asset universe for this project.

Blueprint recommendation: 15-20 liquid, large-cap equities + 2-3 broad/sector ETFs, single
currency (USD), daily frequency. We use US-listed large caps only (not "US/UK" as the blueprint's
looser phrasing allowed) to avoid the ADR/cross-listing complexity that would otherwise creep back
into a project that explicitly scopes out multi-currency/FX risk -- see docs/KNOWN_LIMITATIONS.md.

This universe is inherently survivorship-biased (every name here still exists and is liquid
today). That is a known, accepted MVP-scope limitation, not an oversight -- correcting it would
require point-in-time index-constituent data that is not freely available. Documented here and in
docs/KNOWN_LIMITATIONS.md.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AssetSpec:
    ticker: str
    name: str
    asset_class: str  # EQUITY | ETF
    sector: str


EQUITIES: tuple[AssetSpec, ...] = (
    AssetSpec("AAPL", "Apple Inc.", "EQUITY", "Technology"),
    AssetSpec("MSFT", "Microsoft Corporation", "EQUITY", "Technology"),
    AssetSpec("GOOGL", "Alphabet Inc.", "EQUITY", "Technology"),
    AssetSpec("AMZN", "Amazon.com Inc.", "EQUITY", "Consumer Discretionary"),
    AssetSpec("META", "Meta Platforms Inc.", "EQUITY", "Technology"),
    AssetSpec("NVDA", "NVIDIA Corporation", "EQUITY", "Technology"),
    AssetSpec("JPM", "JPMorgan Chase & Co.", "EQUITY", "Financials"),
    AssetSpec("BAC", "Bank of America Corp.", "EQUITY", "Financials"),
    AssetSpec("JNJ", "Johnson & Johnson", "EQUITY", "Healthcare"),
    AssetSpec("UNH", "UnitedHealth Group Inc.", "EQUITY", "Healthcare"),
    AssetSpec("PG", "Procter & Gamble Co.", "EQUITY", "Consumer Staples"),
    AssetSpec("KO", "Coca-Cola Co.", "EQUITY", "Consumer Staples"),
    AssetSpec("PEP", "PepsiCo Inc.", "EQUITY", "Consumer Staples"),
    AssetSpec("WMT", "Walmart Inc.", "EQUITY", "Consumer Staples"),
    AssetSpec("XOM", "Exxon Mobil Corp.", "EQUITY", "Energy"),
    AssetSpec("CVX", "Chevron Corp.", "EQUITY", "Energy"),
    AssetSpec("DIS", "Walt Disney Co.", "EQUITY", "Communication Services"),
)

ETFS: tuple[AssetSpec, ...] = (
    AssetSpec("XLF", "Financial Select Sector SPDR Fund", "ETF", "Financials"),
    AssetSpec("XLK", "Technology Select Sector SPDR Fund", "ETF", "Technology"),
    AssetSpec("XLE", "Energy Select Sector SPDR Fund", "ETF", "Energy"),
)

UNIVERSE: tuple[AssetSpec, ...] = EQUITIES + ETFS
TICKERS: tuple[str, ...] = tuple(a.ticker for a in UNIVERSE)
