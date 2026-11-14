"""市場流動性／恐慌指標：先看流動性與籌碼結構，再談價格（巨人傑 2026-11 的做法，筆記 knowledge/methods/巨人傑-盤勢操作與槓桿.md）。

他在 11/6 前後的說法：重點不是護盤買了多少，而是化解「量縮的流動性風險」；沒有流動性，融資想減肥減不掉、無量下跌、多殺多；
他看的是跌停家數（「破百家跌停」）、成交量是否萎縮、當沖比重、融資減肥的速度。

這裡用「全市場日行情」（上市＋上櫃，tw_daily.fetch_day_all）能算的部分：跌停家數、漲停家數、上漲／下跌家數、成交值相對近 20 日均值。
融資餘額與當沖比重我們還沒有資料來源（待查證 TWSE／TPEx 的對應端點），先不算。

狀態：恐慌（跌停家數 ≥ panic_limit_down）／警戒（跌停 ≥ warn_limit_down，或成交值 < 20 日均的 thin_turnover_ratio 且下跌家數多於上漲）／
回穩（近 recover_window 個交易日出現過恐慌或警戒，今天跌停 ≤ recover_limit_down 且上漲家數 ≥ 下跌家數）／正常。
門檻都是**暫定值**（settings.yaml 的 market_stress），累積幾週實際資料後再校準。每天一筆存 state/market_stress.json。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .. import config
from ..utils import ROOT

STATE_PATH = ROOT / "state" / "market_stress.json"
DEFAULTS = {"enabled": True, "panic_limit_down": 100, "warn_limit_down": 30, "recover_limit_down": 10, "recover_window": 5,
            "thin_turnover_ratio": 0.8, "min_history": 5, "limit_pct": 9.5, "keep_days": 60}


def settings() -> dict:
    return {**DEFAULTS, **((config.settings().get("market_stress") or {}))}


def _common_stock(code: str) -> bool:
    """一般股票（4 碼數字、不是 0 開頭的 ETF／受益憑證）；權證、特別股、債券 ETF 等不算。"""
    return len(code) == 4 and code.isdigit() and not code.startswith("0")


def day_stats(df: pd.DataFrame, cfg: dict | None = None) -> dict:
    """全市場日行情 → {n, ld（跌停家數）, lu（漲停家數）, up, down, value（一般股票成交值）}。
    漲跌停以「漲跌幅 ≤ −limit_pct%／≥ +limit_pct%」近似（交易所的漲跌停價有整數檔位，實際在 ±9.5～10% 之間）。"""
    cfg = cfg or settings()
    if df is None or df.empty:
        return {"n": 0, "ld": 0, "lu": 0, "up": 0, "down": 0, "value": 0.0}
    d = df[df["code"].astype(str).map(_common_stock)].copy()
    d = d[(d["volume"].fillna(0) > 0) & (d["close"].fillna(0) > 0)]
    pct = d["change"] / (d["close"] - d["change"]) * 100
    lim = float(cfg["limit_pct"])
    return {"n": int(len(d)), "ld": int((pct <= -lim).sum()), "lu": int((pct >= lim).sum()),
            "up": int((pct > 0).sum()), "down": int((pct < 0).sum()), "value": float(d["value"].fillna(0).sum())}


def load(path: Path | None = None) -> list[dict]:
    try:
        d = json.loads((path or STATE_PATH).read_text(encoding="utf-8"))
        return [x for x in d.get("days", []) if isinstance(x, dict) and x.get("d")]
    except (OSError, ValueError, AttributeError):
        return []


def classify(prev: list[dict], today: dict, cfg: dict | None = None) -> tuple[str, list[str]]:
    """prev＝今天之前的紀錄（舊到新）；today＝day_stats 結果。回傳（狀態, 理由）。"""
    cfg = cfg or settings()
    reasons: list[str] = []
    ld, up, down = today["ld"], today["up"], today["down"]
    vals = [x["value"] for x in prev[-20:] if x.get("value")]
    ratio = today["value"] / (sum(vals) / len(vals)) if len(vals) >= int(cfg["min_history"]) and today["value"] else None
    if ld >= int(cfg["panic_limit_down"]):
        return "恐慌", [f"跌停 {ld} 家（≥ {cfg['panic_limit_down']}）"] + ([f"成交值只有 20 日均的 {ratio:.2f} 倍（無量）"] if ratio and ratio < cfg["thin_turnover_ratio"] else [])
    thin = ratio is not None and ratio < float(cfg["thin_turnover_ratio"]) and down > up
    if ld >= int(cfg["warn_limit_down"]) or thin:
        if ld >= int(cfg["warn_limit_down"]):
            reasons.append(f"跌停 {ld} 家（≥ {cfg['warn_limit_down']}）")
        if thin:
            reasons.append(f"量縮下跌：成交值 20 日均的 {ratio:.2f} 倍、下跌 {down} 家多於上漲 {up} 家")
        return "警戒", reasons
    recent = prev[-int(cfg["recover_window"]):]
    if any(x.get("level") in ("恐慌", "警戒") for x in recent) and ld <= int(cfg["recover_limit_down"]) and up >= down:
        return "回穩", [f"近 {cfg['recover_window']} 個交易日出現過恐慌或警戒，今天跌停 {ld} 家、上漲 {up} 家 ≥ 下跌 {down} 家"]
    return "正常", []


def record(day: str, stats: dict, path: Path | None = None, cfg: dict | None = None) -> dict:
    """把這一天存進狀態檔（同一天重跑只覆蓋）並回傳 {"day","level","reasons",**stats}。"""
    cfg = cfg or settings()
    path = path or STATE_PATH
    days = [x for x in load(path) if x["d"] != day]
    prev = [x for x in days if x["d"] < day]
    level, reasons = classify(prev, stats, cfg)
    row = {"d": day, **stats, "level": level, "reasons": reasons}
    days = (days + [row])
    days.sort(key=lambda x: x["d"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"days": days[-int(cfg["keep_days"]):]}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return {"day": day, "level": level, "reasons": reasons, **stats}


ICON = {"恐慌": "🔴", "警戒": "🟠", "回穩": "🟢", "正常": "⚪"}
HINT = {"恐慌": "先確保部位還在（降槓桿、保現金）；這種大家不想看盤的時候是做研究的好時機（可跑 panic-watch 看研究過的標的）。",
        "警戒": "流動性在變差，槓桿別往上加，留意量縮與跌停家數是否擴大。",
        "回穩": "恐慌後出現回穩跡象：他的做法是這時才開始「試探」重新加槓；判斷錯就立刻退回低槓桿。",
        "正常": ""}


def text(r: dict) -> str:
    lines = [f"{ICON.get(r['level'], '')} 市場流動性：{r['level']}｜跌停 {r['ld']} 家、漲停 {r['lu']} 家、上漲 {r['up']}／下跌 {r['down']} 家"]
    lines += [f"　・{x}" for x in r.get("reasons", [])]
    if HINT.get(r["level"]):
        lines.append("　" + HINT[r["level"]])
    return "\n".join(lines)
