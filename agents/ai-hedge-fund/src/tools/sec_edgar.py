"""Free fundamentals data sourced directly from SEC EDGAR's XBRL company-facts API.

Used as a zero-cost fallback for get_financial_metrics/search_line_items/get_market_cap
in src/tools/api.py when no FINANCIAL_DATASETS_API_KEY is configured. Ratio fields and
derived line items (total_debt, ebit, ebitda, free_cash_flow, working_capital, ...) are
computed locally from raw XBRL facts; SEC does not report them directly.
"""

import os
from datetime import datetime, timedelta

import requests

from src.data.models import FinancialMetrics, LineItem
from src.tools.api import get_prices

SEC_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

_ticker_to_cik: dict[str, str] | None = None
_company_facts_cache: dict[str, dict] = {}

# name -> (candidate us-gaap XBRL tags in priority order, "flow" | "instant")
# "flow" = duration facts (income statement / cash flow); "instant" = point-in-time
# balance-sheet facts. Tag lists are ordered fallbacks since filers tag the same
# concept differently depending on company/era.
CONCEPT_MAP: dict[str, tuple[list[str], str]] = {
    "revenue": (["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "SalesRevenueGoodsNet"], "flow"),
    "net_income": (["NetIncomeLoss", "ProfitLoss"], "flow"),
    "operating_income": (["OperatingIncomeLoss"], "flow"),
    "gross_profit": (["GrossProfit"], "flow"),
    "operating_expense": (["OperatingExpenses", "CostsAndExpenses"], "flow"),
    "research_and_development": (["ResearchAndDevelopmentExpense"], "flow"),
    "depreciation_and_amortization": (["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet", "Depreciation"], "flow"),
    "capital_expenditure": (["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsForCapitalImprovements"], "flow"),
    "interest_expense": (["InterestExpense", "InterestExpenseDebt"], "flow"),
    "dividends_and_other_cash_distributions": (["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"], "flow"),
    "operating_cash_flow": (["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"], "flow"),
    "proceeds_from_equity_issuance": (["ProceedsFromIssuanceOfCommonStock"], "flow"),
    "repurchase_of_equity": (["PaymentsForRepurchaseOfCommonStock"], "flow"),
    "income_tax_expense": (["IncomeTaxExpenseBenefit"], "flow"),
    "pretax_income": (
        [
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        ],
        "flow",
    ),
    "earnings_per_share": (["EarningsPerShareDiluted", "EarningsPerShareBasic"], "flow"),
    "total_assets": (["Assets"], "instant"),
    "total_liabilities": (["Liabilities"], "instant"),
    "shareholders_equity": (["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"], "instant"),
    "cash_and_equivalents": (["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"], "instant"),
    "current_assets": (["AssetsCurrent"], "instant"),
    "current_liabilities": (["LiabilitiesCurrent"], "instant"),
    "long_term_debt": (["LongTermDebtNoncurrent", "LongTermDebt"], "instant"),
    "short_term_debt": (["LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings"], "instant"),
    "outstanding_shares": (["CommonStockSharesOutstanding"], "instant"),
}

# Derived names computed from CONCEPT_MAP values rather than mapped directly to a tag.
_DERIVED_NAMES = {
    "total_debt",
    "working_capital",
    "ebit",
    "ebitda",
    "free_cash_flow",
    "issuance_or_purchase_of_equity_shares",
    "book_value_per_share",
}


def _headers() -> dict:
    user_agent = os.environ.get("SEC_EDGAR_USER_AGENT", "ai-hedge-fund research contact@example.com")
    return {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}


def get_cik(ticker: str) -> str | None:
    """Resolve a ticker to its 10-digit zero-padded SEC CIK, via SEC's free ticker map."""
    global _ticker_to_cik
    if _ticker_to_cik is None:
        try:
            response = requests.get(SEC_TICKER_MAP_URL, headers=_headers(), timeout=15)
        except requests.RequestException:
            return None
        if response.status_code != 200:
            return None
        _ticker_to_cik = {entry["ticker"].upper(): str(entry["cik_str"]).zfill(10) for entry in response.json().values()}
    return _ticker_to_cik.get(ticker.upper())


def get_company_facts(cik: str) -> dict:
    """Fetch (and cache) all historical XBRL facts for a company in one request."""
    if cik in _company_facts_cache:
        return _company_facts_cache[cik]
    try:
        response = requests.get(SEC_COMPANY_FACTS_URL.format(cik=cik), headers=_headers(), timeout=30)
    except requests.RequestException:
        return {}
    if response.status_code != 200:
        return {}
    data = response.json()
    _company_facts_cache[cik] = data
    return data


def _facts_for_tag(facts: dict, tag: str, taxonomy: str = "us-gaap") -> list[dict]:
    node = facts.get("facts", {}).get(taxonomy, {}).get(tag)
    if not node:
        return []
    units = node.get("units", {})
    for unit_key in ("USD", "USD/shares", "shares", "pure"):
        if unit_key in units:
            return units[unit_key]
    for entries in units.values():
        return entries
    return []


def _series_for_concepts(facts: dict, tags: list[str]) -> list[dict]:
    # Merge across all candidate tags rather than stopping at the first with any
    # data — filers change which tag they use for the same concept over time
    # (e.g. Apple moved off the plain "Revenues" tag around fiscal 2018), so
    # picking only one tag silently truncates history to whichever era it covers.
    combined = []
    for tag in tags:
        combined.extend(_facts_for_tag(facts, tag))
    return combined


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def _duration_days(entry: dict) -> int | None:
    start, end = entry.get("start"), entry.get("end")
    if not start or not end:
        return None
    return (_parse_date(end) - _parse_date(start)).days


_ANNUAL_DURATION_DAYS = (330, 385)
_QUARTERLY_DURATION_DAYS = (75, 100)


def _filter_by_duration(entries: list[dict], period: str) -> list[dict]:
    # A 10-Q filing reports BOTH the 3-month quarter AND the year-to-date figure
    # as separate facts that can share the same period-end — without this filter
    # a quarter's revenue could get matched against a YTD operating income (or
    # vice versa), badly distorting ratios like margins.
    lo, hi = _ANNUAL_DURATION_DAYS if period == "annual" else _QUARTERLY_DURATION_DAYS
    filtered = [e for e in entries if (days := _duration_days(e)) is not None and lo <= days <= hi]
    return filtered if filtered else entries


def _filter_and_sort(entries: list[dict], end_date: str, forms: set[str] | None) -> list[dict]:
    end_dt = _parse_date(end_date)
    filtered = [e for e in entries if e.get("end") and _parse_date(e["end"]) <= end_dt]
    if forms:
        narrowed = [e for e in filtered if e.get("form") in forms]
        if narrowed:
            filtered = narrowed
    # Dedupe by period-end, keeping whichever filing was filed most recently (latest restatement)
    by_end: dict[str, dict] = {}
    for entry in filtered:
        key = entry["end"]
        if key not in by_end or entry.get("filed", "") > by_end[key].get("filed", ""):
            by_end[key] = entry
    return sorted(by_end.values(), key=lambda e: e["end"], reverse=True)


def get_flow_series(facts: dict, tags: list[str], period: str, end_date: str, limit: int) -> list[dict]:
    entries = _series_for_concepts(facts, tags)
    if not entries:
        return []

    if period == "annual":
        candidates = _filter_by_duration(entries, "annual")
        result = _filter_and_sort(candidates, end_date, forms={"10-K", "10-K/A"})
        return result[:limit] if result else _filter_and_sort(candidates, end_date, forms=None)[:limit]

    if period == "quarterly":
        candidates = _filter_by_duration(entries, "quarterly")
        result = _filter_and_sort(candidates, end_date, forms={"10-Q", "10-Q/A"})
        return result[:limit] if result else _filter_and_sort(candidates, end_date, forms=None)[:limit]

    # "ttm": sum trailing 4 quarters into rolling windows. Approximation — if fewer than
    # 4 quarterly data points are available, fall back to the latest annual figure(s).
    quarterly_candidates = _filter_by_duration(entries, "quarterly")
    quarterly = _filter_and_sort(quarterly_candidates, end_date, forms={"10-Q", "10-Q/A"})
    if len(quarterly) < 4:
        annual_candidates = _filter_by_duration(entries, "annual")
        return _filter_and_sort(annual_candidates, end_date, forms={"10-K", "10-K/A"})[:limit]
    windows = []
    for i in range(min(limit, len(quarterly) - 3)):
        window = quarterly[i : i + 4]
        windows.append({"end": window[0]["end"], "val": sum(w["val"] for w in window), "form": "TTM", "filed": window[0].get("filed", "")})
    return windows


def get_instant_series(facts: dict, tags: list[str], end_date: str, limit: int) -> list[dict]:
    entries = _series_for_concepts(facts, tags)
    if not entries:
        return []
    return _filter_and_sort(entries, end_date, forms=None)[:limit]


def _resolve_raw(facts: dict, name: str, period: str, end_date: str) -> float | None:
    mapping = CONCEPT_MAP.get(name)
    if mapping is None:
        return None
    tags, kind = mapping
    series = get_flow_series(facts, tags, period, end_date, limit=1) if kind == "flow" else get_instant_series(facts, tags, end_date, limit=1)
    if not series:
        # dei:EntityCommonStockSharesOutstanding fallback for share count when the
        # us-gaap tag is missing (some filers only report it in the dei taxonomy).
        if name == "outstanding_shares":
            dei_entries = _facts_for_tag(facts, "EntityCommonStockSharesOutstanding", taxonomy="dei")
            dei_series = _filter_and_sort(dei_entries, end_date, forms=None)[:1]
            return dei_series[0]["val"] if dei_series else None
        return None
    return series[0]["val"]


def _resolve_derived(facts: dict, name: str, period: str, end_date: str) -> float | None:
    if name == "total_debt":
        lt = _resolve_raw(facts, "long_term_debt", period, end_date)
        st = _resolve_raw(facts, "short_term_debt", period, end_date)
        if lt is None and st is None:
            return None
        return (lt or 0.0) + (st or 0.0)

    if name == "working_capital":
        ca = _resolve_raw(facts, "current_assets", period, end_date)
        cl = _resolve_raw(facts, "current_liabilities", period, end_date)
        return ca - cl if ca is not None and cl is not None else None

    if name == "ebit":
        operating_income = _resolve_raw(facts, "operating_income", period, end_date)
        if operating_income is not None:
            return operating_income
        net_income = _resolve_raw(facts, "net_income", period, end_date)
        if net_income is None:
            return None
        interest = _resolve_raw(facts, "interest_expense", period, end_date) or 0.0
        tax = _resolve_raw(facts, "income_tax_expense", period, end_date) or 0.0
        return net_income + interest + tax

    if name == "ebitda":
        ebit = _resolve_derived(facts, "ebit", period, end_date)
        if ebit is None:
            return None
        da = _resolve_raw(facts, "depreciation_and_amortization", period, end_date) or 0.0
        return ebit + da

    if name == "free_cash_flow":
        ocf = _resolve_raw(facts, "operating_cash_flow", period, end_date)
        if ocf is None:
            return None
        capex = _resolve_raw(facts, "capital_expenditure", period, end_date) or 0.0
        return ocf - abs(capex)

    if name == "issuance_or_purchase_of_equity_shares":
        issued = _resolve_raw(facts, "proceeds_from_equity_issuance", period, end_date) or 0.0
        repurchased = _resolve_raw(facts, "repurchase_of_equity", period, end_date) or 0.0
        return issued - repurchased

    if name == "book_value_per_share":
        equity = _resolve_raw(facts, "shareholders_equity", period, end_date)
        shares = _resolve_raw(facts, "outstanding_shares", period, end_date)
        return equity / shares if equity is not None and shares else None

    return None


def _resolve_field_value(facts: dict, name: str, period: str, end_date: str) -> float | None:
    if name in _DERIVED_NAMES:
        return _resolve_derived(facts, name, period, end_date)
    return _resolve_raw(facts, name, period, end_date)


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or not denominator:
        return None
    return numerator / denominator


def _growth(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None or not prior:
        return None
    return (current - prior) / abs(prior)


def _nearest_price(prices: list, target_date: str) -> float | None:
    if not prices:
        return None
    target_dt = _parse_date(target_date)
    on_or_before = [p for p in prices if _parse_date(p.time) <= target_dt]
    if on_or_before:
        return on_or_before[-1].close
    return prices[0].close


def _revenue_anchor_series(facts: dict, period: str, end_date: str, limit: int) -> list[dict]:
    tags, _ = CONCEPT_MAP["revenue"]
    series = get_flow_series(facts, tags, period, end_date, limit)
    if series:
        return series
    tags, _ = CONCEPT_MAP["net_income"]
    return get_flow_series(facts, tags, period, end_date, limit)


def build_line_items(ticker: str, requested_items: list[str], end_date: str, period: str = "ttm", limit: int = 10) -> list[LineItem]:
    cik = get_cik(ticker)
    if not cik:
        return []
    facts = get_company_facts(cik)
    if not facts:
        return []

    anchor_series = _revenue_anchor_series(facts, period, end_date, limit)
    if not anchor_series:
        return []

    results = []
    for anchor in anchor_series:
        period_end = anchor["end"]
        values = {name: _resolve_field_value(facts, name, period, period_end) for name in requested_items}
        results.append(LineItem(ticker=ticker, report_period=period_end, period=period, currency="USD", **values))
    return results


# Raw/derived names needed to compute every FinancialMetrics ratio field the agents read.
_METRICS_INPUT_NAMES = [
    "revenue",
    "net_income",
    "gross_profit",
    "operating_income",
    "shareholders_equity",
    "total_assets",
    "current_assets",
    "current_liabilities",
    "total_debt",
    "cash_and_equivalents",
    "outstanding_shares",
    "earnings_per_share",
    "interest_expense",
    "income_tax_expense",
    "pretax_income",
    "ebit",
    "ebitda",
    "free_cash_flow",
]


def build_financial_metrics(ticker: str, end_date: str, period: str = "ttm", limit: int = 10) -> list[FinancialMetrics]:
    cik = get_cik(ticker)
    if not cik:
        return []
    facts = get_company_facts(cik)
    if not facts:
        return []

    anchor_series = _revenue_anchor_series(facts, period, end_date, limit)
    if not anchor_series:
        return []

    price_start = (_parse_date(anchor_series[-1]["end"]) - timedelta(days=14)).strftime("%Y-%m-%d")
    prices = get_prices(ticker, price_start, end_date)

    results = []
    for i, anchor in enumerate(anchor_series):
        period_end = anchor["end"]
        current = {name: _resolve_field_value(facts, name, period, period_end) for name in _METRICS_INPUT_NAMES}

        prior_end = anchor_series[i + 1]["end"] if i + 1 < len(anchor_series) else None
        prior = (
            {name: _resolve_field_value(facts, name, period, prior_end) for name in ("revenue", "net_income", "shareholders_equity", "earnings_per_share", "free_cash_flow")}
            if prior_end
            else {}
        )

        price = _nearest_price(prices, period_end)
        shares = current["outstanding_shares"]
        market_cap = price * shares if price and shares else None
        book_value_per_share = _safe_div(current["shareholders_equity"], shares)
        enterprise_value = (market_cap + (current["total_debt"] or 0.0) - (current["cash_and_equivalents"] or 0.0)) if market_cap is not None else None

        # Effective tax rate: derived from reported tax/pretax income when available,
        # else a flat statutory-rate approximation. Only used for ROIC below.
        tax_rate = 0.21
        if current["pretax_income"]:
            implied_rate = _safe_div(current["income_tax_expense"], current["pretax_income"])
            if implied_rate is not None and 0 <= implied_rate <= 0.6:
                tax_rate = implied_rate
        invested_capital = None
        if current["total_debt"] is not None and current["shareholders_equity"] is not None:
            invested_capital = current["total_debt"] + current["shareholders_equity"] - (current["cash_and_equivalents"] or 0.0)
        roic = _safe_div(current["ebit"] * (1 - tax_rate), invested_capital) if current["ebit"] is not None and invested_capital else None

        results.append(
            FinancialMetrics(
                ticker=ticker,
                report_period=period_end,
                period=period,
                currency="USD",
                market_cap=market_cap,
                enterprise_value=enterprise_value,
                price_to_earnings_ratio=_safe_div(price, _safe_div(current["net_income"], shares)) if price else None,
                price_to_book_ratio=_safe_div(price, book_value_per_share) if price else None,
                price_to_sales_ratio=_safe_div(market_cap, current["revenue"]),
                enterprise_value_to_ebitda_ratio=_safe_div(enterprise_value, current["ebitda"]),
                peg_ratio=_safe_div(_safe_div(price, _safe_div(current["net_income"], shares)), _growth(current["net_income"], prior.get("net_income")) * 100 if _growth(current["net_income"], prior.get("net_income")) else None) if price else None,
                gross_margin=_safe_div(current["gross_profit"], current["revenue"]),
                operating_margin=_safe_div(current["operating_income"], current["revenue"]),
                net_margin=_safe_div(current["net_income"], current["revenue"]),
                return_on_equity=_safe_div(current["net_income"], current["shareholders_equity"]),
                return_on_invested_capital=roic,
                asset_turnover=_safe_div(current["revenue"], current["total_assets"]),
                current_ratio=_safe_div(current["current_assets"], current["current_liabilities"]),
                debt_to_equity=_safe_div(current["total_debt"], current["shareholders_equity"]),
                interest_coverage=_safe_div(current["ebit"], current["interest_expense"]),
                revenue_growth=_growth(current["revenue"], prior.get("revenue")),
                earnings_growth=_growth(current["net_income"], prior.get("net_income")),
                book_value_growth=_growth(current["shareholders_equity"], prior.get("shareholders_equity")),
                earnings_per_share_growth=_growth(current["earnings_per_share"], prior.get("earnings_per_share")),
                free_cash_flow_growth=_growth(current["free_cash_flow"], prior.get("free_cash_flow")),
                earnings_per_share=current["earnings_per_share"],
                book_value_per_share=book_value_per_share,
                free_cash_flow_per_share=_safe_div(current["free_cash_flow"], shares),
                # Not read by any analyst agent (confirmed by usage audit) — no SEC
                # mapping built for these; present as None to satisfy the model.
                enterprise_value_to_revenue_ratio=None,
                free_cash_flow_yield=None,
                return_on_assets=None,
                inventory_turnover=None,
                receivables_turnover=None,
                days_sales_outstanding=None,
                operating_cycle=None,
                working_capital_turnover=None,
                quick_ratio=None,
                cash_ratio=None,
                operating_cash_flow_ratio=None,
                debt_to_assets=None,
                operating_income_growth=None,
                ebitda_growth=None,
                payout_ratio=None,
            )
        )
    return results


def build_market_cap(ticker: str, end_date: str) -> float | None:
    cik = get_cik(ticker)
    if not cik:
        return None
    facts = get_company_facts(cik)
    if not facts:
        return None
    shares = _resolve_raw(facts, "outstanding_shares", "instant", end_date)
    if not shares:
        return None
    price_start = (_parse_date(end_date) - timedelta(days=14)).strftime("%Y-%m-%d")
    prices = get_prices(ticker, price_start, end_date)
    price = _nearest_price(prices, end_date)
    return price * shares if price else None
