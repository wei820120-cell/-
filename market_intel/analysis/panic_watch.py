"""恐慌日研究清單：已研究過、當初看好（標註「受惠」）、現在價格比研究時更低的個股，附「邏輯還在嗎」要檢查的催化與風險。

巨人傑的說法（2026-11-13）：「研究的腳步絕對不能慢，大家都不想看盤的時刻，反而是做研究的最佳良機」；
11/5：績優個股「買一張未來就是賺一張，前提是你部位還在」。所以恐慌時的順序是：先確保部位（降槓桿、保現金），再回頭看研究過的標的
有沒有因為流動性殺出來變便宜——前提是研究時的邏輯沒有被打破。

這份清單**不是買進建議**：只列出「研究過＋價格回落」，每檔附上當初研究寫的催化與風險（＝邏輯被打破的條件），由人判斷。
價格由呼叫端用 Yahoo 日 K 取得（雲端沙盒抓不到，在 GitHub 上跑）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .research_scoreboard import _dates, load_studies

DROP_PCT = 12.0


def drawdown(close: pd.Series, date: str) -> dict | None:
    """研究日（含）前最後一個收盤為基準。回傳 {"base","last","peak","since","dd","days"}：since＝現價相對基準 %，
    dd＝現價相對研究日後（含基準）最高收盤的回落 %，days＝研究日後已有幾個交易日；基準找不到回傳 None。"""
    close = close.dropna()
    if close.empty:
        return None
    idx = _dates(close)
    pos = idx.searchsorted(pd.Timestamp(date), side="right") - 1
    if pos < 0:
        return None
    base = float(close.iloc[pos])
    if not base:
        return None
    after = close.iloc[pos:]
    peak = float(after.max())
    last = float(close.iloc[-1])
    return {"base": base, "last": last, "peak": peak, "since": (last / base - 1) * 100, "dd": (last / peak - 1) * 100,
            "days": len(close) - 1 - pos}


def load_details(root: Path, topics: list[str]) -> dict[str, dict]:
    """每篇研究的催化、風險（取前幾項）。"""
    out = {}
    for t in topics:
        try:
            d = json.loads((root / "research" / "data" / f"{t}.json").read_text(encoding="utf-8"))
            out[t] = {"catalysts": [str(x) for x in (d.get("catalysts") or [])][:3], "risks": [str(x) for x in (d.get("risks") or [])][:3]}
        except (OSError, ValueError):
            out[t] = {"catalysts": [], "risks": []}
    return out


def candidates(studies: list[dict], prices: dict[str, pd.Series], details: dict[str, dict], names: dict[str, str] | None = None,
               drop_pct: float = DROP_PCT, impacts: tuple[str, ...] = ("受惠",), min_days: int = 1,
               revenue: dict[str, dict] | None = None, min_yoy: float | None = None) -> list[dict]:
    """每檔個股（同一檔在多篇研究時合併）：現價相對研究日 ≤ −drop_pct%，或相對研究後高點回落 ≥ drop_pct%。回落最多的排前面。
    給 revenue（tw_daily.load_revenue）時附上最新月營收年增；再給 min_yoy 就只留年增 ≥ min_yoy 的（股價回落、基本面還在成長＝流動性殺出來的候選；
    沒有營收資料的略過）。"""
    names = names or {}
    per_code: dict[str, list[tuple[dict, dict]]] = {}
    for st in studies:
        for code, impact in st["picks"].items():
            if impact not in impacts or code not in prices:
                continue
            m = drawdown(prices[code], st["date"])
            if m and m["days"] >= min_days:
                per_code.setdefault(code, []).append((st, m))
    best: dict[str, dict] = {}
    for code, items in per_code.items():
        hit = [(st, m) for st, m in items if m["since"] <= -drop_pct or m["dd"] <= -drop_pct]
        if not hit:
            continue
        st0, m0 = min(hit, key=lambda x: x[1]["dd"])           # 回落最多的那一篇當代表；列出所有提到它的研究
        rv = (revenue or {}).get(code) or {}
        if min_yoy is not None and (rv.get("yoy") is None or rv["yoy"] < min_yoy):
            continue
        best[code] = {"code": code, "name": names.get(code, ""), "topics": [st["topic"] for st, _ in items], "since": m0["since"],
                      "yoy": rv.get("yoy"), "cum_yoy": rv.get("cum_yoy"), "ym": rv.get("ym", ""),
                      "dd": m0["dd"], "last": m0["last"], "base": m0["base"], "date": st0["date"],
                      "details": [details.get(st["topic"], {"catalysts": [], "risks": []}) for st, _ in items]}
    return sorted(best.values(), key=lambda r: r["dd"])


def render(rows: list[dict], level: str | None = None, asof: str = "", drop_pct: float = DROP_PCT, total: int | None = None,
           min_yoy: float | None = None) -> str:
    head = [f"# 恐慌日研究清單（{asof}）", ""]
    if level:
        head.append(f"市場流動性狀態：**{level}**。")
    cond = f"條件：研究過、當初標註「受惠」，現價相對研究日 ≤ −{drop_pct:g}% 或相對研究後高點回落 ≥ {drop_pct:g}%（暫定門檻）"
    if min_yoy is not None and min_yoy > -900:
        cond += f"，且最新月營收年增 ≥ {min_yoy:g}%（價格回落、營收仍在成長）"
    if total is not None and total > len(rows):
        cond += f"。共 {total} 檔符合，只列回落最多的前 {len(rows)} 檔"
    head += [cond + "。", "",
             "> **不是買進建議。** 順序是先確保部位（降槓桿、保現金），再看這份清單：每檔下面列當初研究寫的催化與風險——"
             "風險裡的情況若已經發生，代表邏輯被打破，價格便宜不算數。他的說法是「買一張未來就是賺一張，前提是你部位還在」。", ""]
    if not rows:
        return "\n".join(head + ["（目前沒有符合條件的個股）", ""])
    head += ["| 代號 | 名稱 | 研究日 | 相對研究日 | 相對研究後高點 | 現價 | 最新月營收年增 | 研究題材 |", "|---|---|---|---:|---:|---:|---:|---|"]
    for r in rows:
        yoy = f"{r['yoy']:+.0f}%（{r['ym']}）" if r.get("yoy") is not None else "—"
        head.append(f"| {r['code']} | {r['name']} | {r['date']} | {r['since']:+.1f}% | {r['dd']:+.1f}% | {r['last']:,.1f} | {yoy} | "
                    f"{'、'.join(dict.fromkeys(r['topics']))[:60]} |")
    head += ["", "## 逐檔：邏輯還在嗎？", ""]
    for r in rows:
        cats = list(dict.fromkeys(x for d in r["details"] for x in d["catalysts"]))[:3]
        risks = list(dict.fromkeys(x for d in r["details"] for x in d["risks"]))[:3]
        head.append(f"### {r['code']} {r['name']}（相對研究日 {r['since']:+.1f}%、相對高點 {r['dd']:+.1f}%）")
        head += [f"- 催化：{c}" for c in cats] or ["- 催化：（研究檔沒寫）"]
        head += [f"- 風險（＝邏輯被打破的條件）：{x}" for x in risks] or ["- 風險：（研究檔沒寫）"]
        head.append("")
    return "\n".join(head).rstrip() + "\n"


__all__ = ["drawdown", "candidates", "render", "load_details", "load_studies"]
