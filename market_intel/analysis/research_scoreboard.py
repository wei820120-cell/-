"""研究成績單：每篇研究點名的個股，研究日之後相對大盤的表現——看哪一類研究有用、哪一類只是花力氣。

- 資料：research/index.json（日期、狀態）＋ research/data/<題材>.json（layers 裡每檔個股的 impact＝受惠／受傷／中性／混合）。
- 報酬：研究日（含）前最後一個收盤 → 之後第 h 個交易日的收盤；超額報酬 ＝ 個股報酬 − 同一段時間的大盤報酬。
- 重要的限制（成績單裡會印出來）：研究多半是「資金已經流入、股價已經動了」才排進佇列，所以這不是隨機股票的對照；
  樣本期間短、窗口重疊、同一檔會出現在多篇研究、沒有算交易成本；只能當「哪類研究值得多花力氣」的初步線索。
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime
from pathlib import Path

import pandas as pd

HORIZONS = (5, 10, 20)
BENCH = "^TWII"


def study_type(topic: str) -> str:
    if topic.startswith("供需事件"):
        return "供需事件"
    if "題材與產業" in topic:
        return "個股題材"
    return "產業題材"


def impact_class(text: str | None) -> str:
    """研究裡每檔個股的 impact 是自由文字（「受惠，毛利率創高」「同業，另案研究」…）。歸成 受惠／受傷／中性／混合／其他：
    看開頭，開頭不是這四個字就用「其他」，不去猜整句的意思。"""
    t = (text or "").strip()
    for k in ("受惠", "受傷", "中性", "混合"):
        if t.startswith(k):
            return k
    return "未標註" if not t or t == "未標註" else "其他"


def load_studies(root: Path) -> list[dict]:
    """每篇研究：topic、type、status、date、picks（{code: impact}，同一檔取第一次出現的標註）。沒有日期或沒有個股的略過。"""
    try:
        index = json.loads((root / "research" / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for topic, meta in index.items():
        date = (meta or {}).get("date")
        data_file = root / "research" / "data" / f"{topic}.json"
        picks: dict[str, str] = {}
        try:
            d = json.loads(data_file.read_text(encoding="utf-8"))
            for layer in d.get("layers", []):
                for s in layer.get("tw_stocks", []):
                    code = str(s.get("code") or "").strip()
                    if code and code not in picks:
                        picks[code] = impact_class(s.get("impact"))
        except (OSError, ValueError):
            for code in (meta or {}).get("codes", []):      # 沒有 data 檔就只用索引的代號、方向未標註
                picks.setdefault(str(code), "未標註")
        if date and picks:
            out.append({"topic": topic, "type": study_type(topic), "status": (meta or {}).get("status") or "未標註",
                        "date": date, "picks": picks})
    return out


def _dates(s: pd.Series) -> pd.DatetimeIndex:
    idx = s.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("Asia/Taipei").tz_localize(None)
    return pd.DatetimeIndex(idx).normalize()


def forward_returns(close: pd.Series, date: str, horizons=HORIZONS) -> dict:
    """研究日（含）前最後一個收盤為基準。回傳 {"base": 基準價, "h5": %, "h10": %, "h20": %, "latest": %, "latest_days": 交易日數}；
    基準價找不到（研究日前沒有資料）回傳空 dict；超出已有資料的 h 不放。"""
    close = close.dropna()
    if close.empty:
        return {}
    idx = _dates(close)
    cut = pd.Timestamp(date)
    pos = idx.searchsorted(cut, side="right") - 1          # 研究日（含）前最後一天
    if pos < 0:
        return {}
    base = float(close.iloc[pos])
    if not base:
        return {}
    out = {"base": base}
    for h in horizons:
        if pos + h < len(close):
            out[f"h{h}"] = (float(close.iloc[pos + h]) / base - 1) * 100
    if pos + 1 < len(close):
        out["latest"] = (float(close.iloc[-1]) / base - 1) * 100
        out["latest_days"] = len(close) - 1 - pos
    return out


def build_rows(studies: list[dict], prices: dict[str, pd.Series], bench: pd.Series | None, horizons=HORIZONS) -> list[dict]:
    """每個（研究, 個股）一列：各期間報酬與超額報酬。大盤資料缺時超額＝None。"""
    rows = []
    for st in studies:
        bench_fr = forward_returns(bench, st["date"], horizons) if bench is not None else {}
        for code, impact in st["picks"].items():
            s = prices.get(code)
            if s is None:
                continue
            fr = forward_returns(s, st["date"], horizons)
            if not fr:
                continue
            row = {"topic": st["topic"], "type": st["type"], "status": st["status"], "date": st["date"], "code": code, "impact": impact,
                   "latest_days": fr.get("latest_days", 0)}
            for k in [f"h{h}" for h in horizons] + ["latest"]:
                if k in fr:
                    row[k] = fr[k]
                    row[f"x_{k}"] = fr[k] - bench_fr[k] if k in bench_fr else None
            rows.append(row)
    return rows


def aggregate(rows: list[dict], key: str, metric: str) -> list[dict]:
    """依 key 分組，統計 metric（例如 x_h5＝5 日超額報酬）：樣本數、獨立個股數、平均、中位數、勝率（超額 > 0）。"""
    groups: dict[str, list[dict]] = {}
    for r in rows:
        if r.get(metric) is not None:
            groups.setdefault(str(r[key]), []).append(r)
    out = []
    for g, rs in sorted(groups.items()):
        v = [r[metric] for r in rs]
        out.append({"group": g, "n": len(v), "codes": len({r["code"] for r in rs}), "mean": statistics.fmean(v),
                    "median": statistics.median(v), "hit": sum(1 for x in v if x > 0) / len(v) * 100})
    return out


def _table(title: str, rows: list[dict], metric: str, label: str) -> list[str]:
    stats = aggregate(rows, title, metric)
    if not stats:
        return [f"- {label}：樣本不足", ""]
    lines = [f"**{label}**", "", "| 分組 | 樣本 | 個股 | 平均超額 | 中位數 | 勝率 |", "|---|---:|---:|---:|---:|---:|"]
    for s in stats:
        lines.append(f"| {s['group']} | {s['n']} | {s['codes']} | {s['mean']:+.1f}% | {s['median']:+.1f}% | {s['hit']:.0f}% |")
    return lines + [""]


def render(rows: list[dict], studies: list[dict], asof: datetime | None = None) -> str:
    asof = asof or datetime.now()
    n_studies = len({r["topic"] for r in rows})
    dates = sorted({s["date"] for s in studies})
    lines = [f"# 研究成績單（{asof:%Y-%m-%d} 產生）", "",
             f"研究 {len(studies)} 篇（日期 {dates[0] if dates else '—'}～{dates[-1] if dates else '—'}），有價格資料的 {n_studies} 篇、{len(rows)} 個（研究, 個股）組合。",
             "超額報酬 ＝ 個股報酬 − 同期間加權指數報酬；基準是研究日（含）前最後一個收盤。", "",
             "> **怎麼讀：先看限制。** 研究多半是在「資金已經流入、股價已經動了」之後才排進佇列，所以這不是隨機股票的對照；"
             "樣本期間只有幾週、窗口彼此重疊、同一檔會出現在多篇研究、沒有算交易成本。只能當「哪類研究值得多花力氣」的初步線索，不能當績效。", ""]
    for metric, label in (("x_h5", "5 個交易日超額報酬"), ("x_h10", "10 個交易日超額報酬"), ("x_h20", "20 個交易日超額報酬"),
                          ("x_latest", "到最新收盤的超額報酬（天數不一）")):
        lines += [f"## {label}", ""]
        for key, name in (("type", "依研究類型"), ("impact", "依個股方向標註（受惠／受傷…）"), ("status", "依研究狀態")):
            lines += _table(key, rows, metric, name)
    return "\n".join(lines).rstrip() + "\n"
