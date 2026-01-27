from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Holding:
    description: str
    quantity: float
    currency: str
    market_value: float
    profit_loss: float
    allocation_pct: float
    return_pct: float
    sector: str


def _parse_number(value: str) -> Optional[float]:
    cleaned = value.replace(",", "").replace("%", "").strip().strip('"')
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def load_holdings(path: str) -> List[Holding]:
    """
    Parse StockTrak-style portfolio export.
    Returns holdings with allocation/return percentages.
    """
    holdings: List[Holding] = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header_idx = None
        for idx, row in enumerate(reader):
            if row and row[0].strip() == "Description":
                header_idx = idx
                header = row
                break

        if header_idx is None:
            return holdings

        # Build column index map
        col = {name: i for i, name in enumerate(header)}

        for row in reader:
            if not row or not row[0].strip():
                break
            desc = row[col["Description"]].strip()
            sector = row[col.get("Sectors", -1)].strip() if col.get("Sectors") is not None else ""

            quantity = _parse_number(row[col.get("Quantity", -1)]) or 0.0
            currency = row[col.get("Currency", -1)].strip() if col.get("Currency") is not None else ""
            market_value = _parse_number(row[col.get("MarketValue", -1)]) or 0.0
            profit_loss = _parse_number(row[col.get("ProfitLoss", -1)]) or 0.0
            allocation_pct = _parse_number(row[col.get("Allocation %", -1)]) or 0.0
            return_pct = _parse_number(row[col.get("Return %", -1)]) or 0.0

            holdings.append(
                Holding(
                    description=desc,
                    quantity=quantity,
                    currency=currency,
                    market_value=market_value,
                    profit_loss=profit_loss,
                    allocation_pct=allocation_pct,
                    return_pct=return_pct,
                    sector=sector,
                )
            )

    return holdings


def weights_from_holdings(holdings: List[Holding]) -> Dict[str, float]:
    total = sum(h.market_value for h in holdings)
    if total <= 0:
        return {}
    return {h.description: h.market_value / total for h in holdings}
