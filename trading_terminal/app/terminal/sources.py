"""Extra data sources: SEC EDGAR, FRED, Finnhub, Financial Modeling Prep."""
from __future__ import annotations

import datetime as dt
from functools import lru_cache

import pandas as pd
import requests

from . import config

TIMEOUT = 20


def clean_error(e: Exception) -> str:
    """Error text with API keys removed (request errors include the full URL)."""
    msg = str(e)
    for key in (config.FINNHUB_API_KEY, config.FMP_API_KEY, config.FRED_API_KEY):
        if key:
            msg = msg.replace(key, "***")
    return msg


def _get(url: str, **kw) -> requests.Response:
    r = requests.get(url, timeout=TIMEOUT, **kw)
    r.raise_for_status()
    return r


# ---------- SEC EDGAR (no key; SEC requires a contact email in the User-Agent) ----------
def _sec_headers() -> dict:
    return {"User-Agent": f"TradingTerminal {config.SEC_CONTACT_EMAIL or 'admin@example.com'}"}


@lru_cache(maxsize=1)
def _cik_map() -> dict[str, int]:
    rows = _get("https://www.sec.gov/files/company_tickers.json", headers=_sec_headers()).json()
    return {v["ticker"]: v["cik_str"] for v in rows.values()}


@lru_cache(maxsize=1)
def ticker_names() -> list[tuple[str, str]]:
    """(ticker, company name) for every SEC-registered company, for the search box."""
    rows = _get("https://www.sec.gov/files/company_tickers.json", headers=_sec_headers()).json()
    return [(v["ticker"], v["title"]) for v in rows.values()]


def sec_filings(symbol: str) -> pd.DataFrame:
    """Recent filings: date, form, description, 8-K item codes, link to the document."""
    cik = _cik_map().get(symbol.upper().replace(".", "-"))
    if cik is None:
        return pd.DataFrame()
    recent = _get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", headers=_sec_headers()).json()["filings"]["recent"]
    df = pd.DataFrame(recent)
    df["url"] = [
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{doc}"
        for acc, doc in zip(df["accessionNumber"], df["primaryDocument"])
    ]
    return df.rename(columns={"filingDate": "filed", "reportDate": "period", "primaryDocDescription": "description"})[
        ["filed", "form", "description", "period", "items", "url"]
    ]


# Financial statements from the XBRL data in company filings. Line item -> (concept names to try,
# in order of preference, sign). Companies switch concept names over the years, so each line merges
# every name it has used. sign -1 turns cash outflows (reported as positive payments) negative.
STATEMENTS = {
    "income": {
        "Revenue": (["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
                     "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueGoodsNet",
                     "RevenuesNetOfInterestExpense"], 1),  # last one: banks
        "Cost of revenue": (["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"], 1),
        "Gross profit": (["GrossProfit"], 1),
        "Research & development": (["ResearchAndDevelopmentExpense"], 1),
        "Selling, general & admin": (["SellingGeneralAndAdministrativeExpense"], 1),
        "Operating income": (["OperatingIncomeLoss"], 1),
        "Pretax income": (["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                           "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"], 1),
        "Income tax": (["IncomeTaxExpenseBenefit"], 1),
        "Net income": (["NetIncomeLoss", "ProfitLoss"], 1),
        "EPS (diluted)": (["EarningsPerShareDiluted"], 1),
        "Diluted shares": (["WeightedAverageNumberOfDilutedSharesOutstanding"], 1),
    },
    "balance": {
        "Cash & equivalents": (["CashAndCashEquivalentsAtCarryingValue",
                                "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"], 1),
        "Short-term investments": (["MarketableSecuritiesCurrent", "ShortTermInvestments", "AvailableForSaleSecuritiesCurrent"], 1),
        "Inventory": (["InventoryNet"], 1),
        "Current assets": (["AssetsCurrent"], 1),
        "Total assets": (["Assets"], 1),
        "Current liabilities": (["LiabilitiesCurrent"], 1),
        "Long-term debt": (["LongTermDebtNoncurrent", "LongTermDebt"], 1),
        "Total liabilities": (["Liabilities"], 1),
        "Shareholders' equity": (["StockholdersEquity",
                                  "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"], 1),
    },
    "cashflow": {
        "Operating cash flow": (["NetCashProvidedByUsedInOperatingActivities",
                                 "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"], 1),
        "Capital expenditure": (["PaymentsToAcquirePropertyPlantAndEquipment"], -1),
        "Investing cash flow": (["NetCashProvidedByUsedInInvestingActivities"], 1),
        "Financing cash flow": (["NetCashProvidedByUsedInFinancingActivities"], 1),
        "Dividends paid": (["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"], -1),
        "Share buybacks": (["PaymentsForRepurchaseOfCommonStock"], -1),
        "Stock-based compensation": (["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"], 1),
    },
}
INSTANT = {"balance"}  # balance-sheet items are a value on a date, not over a period


def sec_facts(symbol: str) -> dict:
    """All XBRL facts a company has filed (us-gaap), or {} if it isn't an SEC filer."""
    cik = _cik_map().get(symbol.upper().replace(".", "-"))
    if cik is None:
        return {}
    j = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json", headers=_sec_headers()).json()
    return j.get("facts", {}).get("us-gaap", {})


def _series(facts: dict, concepts: list[str], instant: bool, quarterly: bool) -> dict:
    """{period end date: value} for one line item, merging its concept names (earlier names win ties)."""
    out: dict = {}
    for concept in concepts:
        units = facts.get(concept, {}).get("units", {})
        rows = next((units[u] for u in ("USD", "USD/shares", "shares") if u in units), [])
        best: dict = {}  # end date -> (filed, value): keep the latest filing (it includes restatements)
        quarters, years = {}, {}
        for f in rows:
            end, filed = f.get("end"), f.get("filed", "")
            if instant:
                if "start" in f or (not quarterly and f.get("form") not in ("10-K", "10-K/A")):
                    continue
                if end not in best or filed > best[end][0]:
                    best[end] = (filed, f["val"])
                continue
            if "start" not in f:
                continue
            days = (pd.Timestamp(end) - pd.Timestamp(f["start"])).days
            bucket = years if 330 <= days <= 400 else quarters if 80 <= days <= 100 else None
            if bucket is None:
                continue
            key = (f["start"], end)
            if key not in bucket or filed > bucket[key][0]:
                bucket[key] = (filed, f["val"])
        if not instant:
            if not quarterly:
                best = {e: v for (s, e), v in years.items()}
            else:
                best = {e: v for (s, e), v in quarters.items()}
                # The fourth quarter is rarely reported alone: work it out as the year minus Q1-Q3.
                for (ys, ye), (filed, total) in years.items():
                    if ye in best:
                        continue
                    inside = [v for (s, e), (_, v) in quarters.items() if s >= ys and e < ye]
                    if len(inside) == 3:
                        best[ye] = (filed, total - sum(inside))
        for end, (_, val) in best.items():
            out.setdefault(end, val)
    return out


def sec_statements(symbol: str, statement: str = "income", quarterly: bool = False, periods: int | None = None,
                   facts: dict | None = None) -> pd.DataFrame:
    """A statement as rows = line items, columns = period end dates (newest first), like Yahoo's.
    Pass `facts` (from sec_facts) to build several statements from one download."""
    facts = sec_facts(symbol) if facts is None else facts
    if not facts:
        return pd.DataFrame()
    instant = statement in INSTANT
    lines = {}
    for label, (concepts, sign) in STATEMENTS[statement].items():
        s = _series(facts, concepts, instant, quarterly)
        if s:
            lines[label] = {k: v * sign for k, v in s.items()}
    if statement == "cashflow" and "Operating cash flow" in lines:
        capex = lines.get("Capital expenditure", {})
        lines["Free cash flow"] = {d: v + capex.get(d, 0) for d, v in lines["Operating cash flow"].items()}
    if statement == "income" and "Gross profit" not in lines and {"Revenue", "Cost of revenue"} <= set(lines):
        lines["Gross profit"] = {d: v - lines["Cost of revenue"][d] for d, v in lines["Revenue"].items()
                                 if d in lines["Cost of revenue"]}
    df = pd.DataFrame(lines).T
    if df.empty:
        return df
    df = df[sorted(df.columns, reverse=True)]
    # Keep columns where the headline line is reported (avoids stray dates from one-off filings).
    anchor = {"income": "Revenue", "balance": "Total assets", "cashflow": "Operating cash flow"}[statement]
    if anchor in df.index:
        df = df.loc[:, df.loc[anchor].notna()]
    order = [k for k in [*STATEMENTS[statement], "Free cash flow"] if k in df.index]
    df = df.loc[order]
    return df.iloc[:, : (periods or (12 if quarterly else 15))]


# ---------- FRED (free key) ----------
FRED_SERIES = {
    "Fed funds rate": "DFF",
    "2-year Treasury": "DGS2",
    "10-year Treasury": "DGS10",
    "10y minus 2y spread": "T10Y2Y",
    "30-year mortgage": "MORTGAGE30US",
    "CPI inflation (YoY %)": "CPIAUCSL",
    "Unemployment rate": "UNRATE",
    "Real GDP growth (QoQ ann. %)": "A191RL1Q225SBEA",
    "VIX": "VIXCLS",
    "High-yield credit spread": "BAMLH0A0HYM2",
}


def fred_series(series_id: str, years: int = 5) -> pd.Series:
    start = dt.date.today() - dt.timedelta(days=365 * years + 400)
    params = {"series_id": series_id, "api_key": config.FRED_API_KEY, "file_type": "json", "observation_start": str(start)}
    if series_id == "CPIAUCSL":
        params["units"] = "pc1"  # percent change from a year ago
    obs = _get("https://api.stlouisfed.org/fred/series/observations", params=params).json()["observations"]
    s = pd.Series({pd.Timestamp(o["date"]): o["value"] for o in obs})
    return pd.to_numeric(s, errors="coerce").dropna()


# ---------- Finnhub (free key) ----------
def _finnhub(path: str, **params):
    return _get(f"https://finnhub.io/api/v1{path}", params={**params, "token": config.FINNHUB_API_KEY}).json()


def earnings_calendar(days: int = 14) -> pd.DataFrame:
    today = dt.date.today()
    rows = _finnhub("/calendar/earnings", **{"from": str(today), "to": str(today + dt.timedelta(days=days))})
    df = pd.DataFrame(rows.get("earningsCalendar", []))
    return df.sort_values(["date", "symbol"]) if not df.empty else df


def upcoming_earnings(symbols: list[str], days: int = 45) -> pd.DataFrame:
    """Next scheduled report per symbol (asked one symbol at a time: the all-market calendar is truncated)."""
    today = dt.date.today()
    rows = []
    for s in symbols:
        try:
            got = _finnhub("/calendar/earnings", symbol=s, **{"from": str(today), "to": str(today + dt.timedelta(days=days))})
        except Exception:
            continue
        rows += got.get("earningsCalendar", [])
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.drop_duplicates(["symbol", "date"]).sort_values(["date", "symbol"])
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def earnings_surprises(symbol: str) -> pd.DataFrame:
    return pd.DataFrame(_finnhub("/stock/earnings", symbol=symbol.upper()))


def insider_transactions(symbol: str) -> pd.DataFrame:
    return pd.DataFrame(_finnhub("/stock/insider-transactions", symbol=symbol.upper()).get("data", []))


# ---------- Financial Modeling Prep (free key) ----------
FMP_VIEWS = {
    "Fair value (DCF)": "discounted-cash-flow",
    "Rating": "ratings-snapshot",
    "Financial health scores": "financial-scores",
    "Price target consensus": "price-target-consensus",
    "Ratios (ttm)": "ratios-ttm",
    "Key metrics (ttm)": "key-metrics-ttm",
}


def fmp(endpoint: str, symbol: str) -> dict:
    """First record of an FMP per-symbol endpoint, as a flat dict."""
    rows = _get(
        f"https://financialmodelingprep.com/stable/{endpoint}",
        params={"symbol": symbol.upper(), "apikey": config.FMP_API_KEY},
    ).json()
    if isinstance(rows, dict):
        if "Error Message" in rows:
            raise RuntimeError(rows["Error Message"])
        return rows
    return rows[0] if rows else {}
