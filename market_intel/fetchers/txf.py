"""台指期（TXF）即時報價：期交所行情資訊系統（MIS）getQuoteList，MarketType 0＝一般交易時段（日盤）、1＝盤後（夜盤）。
和 overnight.py 同一個端點（那邊用 MarketType 1 抓盤後）；取成交量最大的單一契約＝近月。
欄位名稱沿用 overnight.mis_night 已在用的 SymbolID／CLastPrice／CTotalVolume／CDate／CTime；
CHighPrice／CLowPrice／COpenPrice 是同一個端點的今日高低開（缺了就只用自己記的報價）。"""
from __future__ import annotations

import logging

from .. import net
from ..overnight import MIS_BODY, MIS_URL, _mis_ts
from ..utils import TW_TZ, pick, to_float

log = logging.getLogger(__name__)


def parse(rows: list[dict]) -> dict | None:
    """MIS 報價列表 → {symbol, price, high, low, open, volume, ts}；沒有可用的近月報價回傳 None。"""
    cands = []
    for r in rows:
        sym = str(pick(r, "SymbolID", default="")).strip()
        last = to_float(pick(r, "CLastPrice"))
        if sym.startswith("TXF") and "/" not in sym and last:
            cands.append((to_float(pick(r, "CTotalVolume")) or 0, sym, last, r))
    if not cands:
        return None
    vol, sym, last, r = max(cands, key=lambda c: c[0])
    return {"symbol": sym, "price": last, "high": to_float(pick(r, "CHighPrice")), "low": to_float(pick(r, "CLowPrice")),
            "open": to_float(pick(r, "COpenPrice")), "volume": vol, "ts": _mis_ts(r, TW_TZ)}


def fetch_rows(night: bool = False) -> list[dict]:
    """MarketType 0＝一般交易時段（日盤）、1＝盤後（夜盤，15:00–隔天 05:00；代號尾碼 -M，日盤是 -F）。"""
    body = dict(MIS_BODY, MarketType="1" if night else "0")
    data = net.post_json(MIS_URL, body, headers={"Referer": "https://mis.taifex.com.tw/futures/",
                                                 "Origin": "https://mis.taifex.com.tw"})
    rows = ((data or {}).get("RtData") or {}).get("QuoteList")
    return rows if isinstance(rows, list) else []


def fetch(night: bool = False) -> dict | None:
    return parse(fetch_rows(night))
