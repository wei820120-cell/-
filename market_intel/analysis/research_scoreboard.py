"""研究成績單：每篇研究點名的個股，研究日之後相對大盤的表現——看哪一類研究有用、哪一類只是花力氣。

- 資料：research/index.json（日期、狀態）＋ research/data/<題材>.json（layers 裡每檔個股的 impact＝受惠／受傷／中性／混合）。
- 報酬：研究日（含）前最後一個收盤 → 之後第 h 個交易日的收盤；超額報酬 ＝ 個股報酬 − 同一段時間的大盤報酬。
- 基準價：研究發布當下記錄的價格（research/entry_prices.json，發布時抓 Yahoo 最新價）；沒有記錄的舊研究用「研究日（含）前最後一個收盤」。
- 對照組：除了加權指數，另用「沒被研究點名的上市櫃股票等權重隨機樣本」（固定種子，每次同一批）算同期間報酬，看研究股有沒有贏過普通股票。
- 分組：研究類型、個股方向標註、研究狀態、觸發來源（資金流入／連動預研／早期訊號／供需新聞／社群…）、證據等級（研究檔的 evidence 欄位，舊研究未標註）。
- 重要的限制（成績單裡會印出來）：研究多半是「資金已經流入、股價已經動了」才排進佇列，所以這不是隨機股票的對照；
  樣本期間短、窗口重疊、同一檔會出現在多篇研究、沒有算交易成本；只能當「哪類研究值得多花力氣」的初步線索。
"""
from __future__ import annotations

import json
import random
import re
import statistics
from datetime import datetime
from pathlib import Path

import pandas as pd

HORIZONS = (5, 10, 20)
BENCH = "^TWII"
MIN_N = 10                  # 樣本少於這個數的分組會標「樣本少」
CONTROL_MIN_STOCKS = 20     # 對照組某期間有價格的股票少於這個數就不算
EVIDENCE_LEVELS = ("官方公告", "數據報告", "媒體報導", "社群傳聞")


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


def trigger_type(text: str | None) -> str:
    """從研究檔的「觸發來源」文字歸類：這份研究是怎麼被排進來的。看前 200 字，不猜整段的意思。"""
    t = (text or "")[:200]
    if re.search(r"threads\.com|Threads|Podcast|股癌|頻道貼文偵測", t):
        return "社群／Podcast"
    if "使用者" in t or "手動" in t or "指定" in t:
        return "手動"
    if "盤後資金流入" in t or "資金流入" in t:
        return "資金流入"
    if "不在任何族群的強勢股" in t:
        return "強勢股（股價先動）"
    if "連動預研" in t:
        return "連動預研"
    if "早期訊號" in t:
        return "早期訊號（未證實新聞）"
    if "供需失衡" in t:
        return "供需新聞"
    if "重大事件" in t:
        return "重大事件新聞"
    if re.match(r"\s*(經濟部|財政部|金管會|證交所|行政院|商務部)", t) or "公告（" in t[:60]:
        return "官方公告"
    return "其他／未記錄" if t.strip() else "未記錄"


def _trigger_of(root: Path, meta: dict) -> str:
    try:
        md = (root / "research" / meta["file"]).read_text(encoding="utf-8")
    except (OSError, KeyError, TypeError):
        return ""
    m = re.search(r"<summary>觸發來源</summary>\s*(.*?)\s*</details>", md, re.S)
    return m.group(1) if m else ""


def load_entry_prices(root: Path) -> dict:
    """發布研究當下記錄的價格：{題材: {"asof": 時間, "bench": 加權指數, "px": {代號: 價格}}}。沒有檔就是空的。"""
    try:
        d = json.loads((root / "research" / "entry_prices.json").read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def load_studies(root: Path) -> list[dict]:
    """每篇研究：topic、type、status、date、trigger_type、evidence、entry、picks（{code: impact}，同一檔取第一次出現的標註）。沒有日期或沒有個股的略過。"""
    try:
        index = json.loads((root / "research" / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    entries = load_entry_prices(root)
    out = []
    for topic, meta in index.items():
        date = (meta or {}).get("date")
        data_file = root / "research" / "data" / f"{topic}.json"
        picks: dict[str, str] = {}
        evidence = (meta or {}).get("evidence")
        try:
            d = json.loads(data_file.read_text(encoding="utf-8"))
            evidence = evidence or d.get("evidence")
            for layer in d.get("layers", []):
                for s in layer.get("tw_stocks", []):
                    code = str(s.get("code") or "").strip()
                    if code and code not in picks:
                        picks[code] = impact_class(s.get("impact"))
        except (OSError, ValueError):
            for code in (meta or {}).get("codes", []):      # 沒有 data 檔就只用索引的代號、方向未標註
                picks.setdefault(str(code), "未標註")
        if date and picks:
            ent = entries.get(topic)
            if not (isinstance(ent, dict) and ent.get("asof", "")[:10] == date):
                ent = None                                  # 記錄日期和研究日期對不上（重新研究過）就不用
            out.append({"topic": topic, "type": study_type(topic), "status": (meta or {}).get("status") or "未標註",
                        "date": date, "picks": picks, "trigger_type": trigger_type(_trigger_of(root, meta)),
                        "evidence": evidence if evidence in EVIDENCE_LEVELS else "未標註", "entry": ent})
    return out


def _dates(s: pd.Series) -> pd.DatetimeIndex:
    idx = s.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("Asia/Taipei").tz_localize(None)
    return pd.DatetimeIndex(idx).normalize()


def forward_returns(close: pd.Series, date: str, horizons=HORIZONS, entry: float | None = None) -> dict:
    """研究日（含）前最後一個收盤為基準；給 entry（發布當下記錄的價格）就改用它當基準價（第 h 天仍照研究日算）。
    回傳 {"base": 基準價, "h5": %, "h10": %, "h20": %, "latest": %, "latest_days": 交易日數}；
    基準價找不到（研究日前沒有資料）回傳空 dict；超出已有資料的 h 不放。"""
    close = close.dropna()
    if close.empty:
        return {}
    idx = _dates(close)
    cut = pd.Timestamp(date)
    pos = idx.searchsorted(cut, side="right") - 1          # 研究日（含）前最後一天
    if pos < 0:
        return {}
    base = float(entry) if entry and entry > 0 else float(close.iloc[pos])
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


def pick_control(listings: dict, exclude: set[str], n: int = 150, seed: int = 20261114) -> list[str]:
    """對照組：沒被研究點名的上市櫃一般股票（4 位數代號），固定種子隨機取 n 檔（每次同一批，成績單前後才能比）。"""
    pool = sorted(c for c, v in listings.items()
                  if re.fullmatch(r"[1-9]\d{3}", c) and (v or {}).get("market") in ("tse", "otc") and c not in exclude)
    if len(pool) <= n:
        return pool
    return sorted(random.Random(seed).sample(pool, n))


def control_returns(prices: dict[str, pd.Series], date: str, horizons=HORIZONS) -> dict:
    """對照組同一研究日、同一期間的等權重平均報酬：{"h5": %, ..., "latest": %}；某個期間有資料的股票不到 CONTROL_MIN_STOCKS 檔就不放。"""
    acc: dict[str, list[float]] = {}
    for s in prices.values():
        for k, v in forward_returns(s, date, horizons).items():
            if k in ("base", "latest_days"):
                continue
            acc.setdefault(k, []).append(v)
    return {k: statistics.fmean(v) for k, v in acc.items() if len(v) >= CONTROL_MIN_STOCKS}


def build_rows(studies: list[dict], prices: dict[str, pd.Series], bench: pd.Series | None, horizons=HORIZONS,
               control: dict[str, pd.Series] | None = None) -> list[dict]:
    """每個（研究, 個股）一列：各期間報酬、對大盤超額（x_）、對等權重對照組超額（e_）。資料缺時對應欄位為 None。
    研究有記錄發布當下的價格就用它當基準（base_src＝記錄），否則用研究日前最後收盤（收盤）。"""
    rows = []
    for st in studies:
        ent = st.get("entry") or {}
        bench_fr = forward_returns(bench, st["date"], horizons, ent.get("bench")) if bench is not None else {}
        ctrl_fr = control_returns(control, st["date"], horizons) if control else {}
        for code, impact in st["picks"].items():
            s = prices.get(code)
            if s is None:
                continue
            entry_px = (ent.get("px") or {}).get(code)
            fr = forward_returns(s, st["date"], horizons, entry_px)
            if not fr:
                continue
            row = {"topic": st["topic"], "type": st["type"], "status": st["status"], "date": st["date"], "code": code, "impact": impact,
                   "trigger_type": st.get("trigger_type", "未記錄"), "evidence": st.get("evidence", "未標註"),
                   "base_src": "記錄" if entry_px else "收盤", "latest_days": fr.get("latest_days", 0)}
            for k in [f"h{h}" for h in horizons] + ["latest"]:
                if k in fr:
                    row[k] = fr[k]
                    row[f"x_{k}"] = fr[k] - bench_fr[k] if k in bench_fr else None
                    row[f"e_{k}"] = fr[k] - ctrl_fr[k] if k in ctrl_fr else None
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


def overall(rows: list[dict], metric: str) -> dict | None:
    """全部列的同一組統計（key 用常數）。沒有樣本回 None。"""
    stats = aggregate([{**r, "_all": "全部"} for r in rows], "_all", metric)
    return stats[0] if stats else None


def _cell(s: dict | None) -> str:
    return "—｜—" if not s else f"{s['mean']:+.1f}%｜{s['hit']:.0f}%"


def _table(key: str, rows: list[dict], horizon: str, label: str, with_control: bool) -> list[str]:
    """一張分組表：每組的樣本、個股數、對大盤的平均超額／勝率，有對照組時再加對等權重對照組的平均超額／勝率。樣本少於 MIN_N 標 ⚠。"""
    xs = {a["group"]: a for a in aggregate(rows, key, f"x_{horizon}")}
    es = {a["group"]: a for a in aggregate(rows, key, f"e_{horizon}")} if with_control else {}
    if not xs and not es:
        return [f"- {label}：樣本不足", ""]
    head = "| 分組 | 樣本 | 個股 | 對大盤：平均超額｜勝率 | 中位數 |"
    sep = "|---|---:|---:|---:|---:|"
    if with_control:
        head += " 對等權重對照組：平均超額｜勝率 |"
        sep += "---:|"
    lines = [f"**{label}**", "", head, sep]
    groups = sorted(set(xs) | set(es))
    allx, alle = overall(rows, f"x_{horizon}"), (overall(rows, f"e_{horizon}") if with_control else None)

    def line(name: str, x: dict | None, e: dict | None) -> str:
        base = x or e
        flag = " ⚠樣本少" if base and base["n"] < MIN_N else ""
        med = f"{x['median']:+.1f}%" if x else "—"
        out = f"| {name}{flag} | {base['n'] if base else 0} | {base['codes'] if base else 0} | {_cell(x)} | {med} |"
        return out + (f" {_cell(e)} |" if with_control else "")

    for g in groups:
        lines.append(line(g, xs.get(g), es.get(g)))
    lines.append(line("**全部**", allx, alle))
    return lines + [""]


GROUPS = (("type", "依研究類型"), ("impact", "依個股方向標註（受惠／受傷…）"), ("status", "依研究狀態"),
          ("trigger_type", "依觸發來源（這份研究是怎麼排進來的）"), ("evidence", "依證據等級（新研究才有標，舊的未標註）"))


def render(rows: list[dict], studies: list[dict], asof: datetime | None = None, control_n: int = 0) -> str:
    asof = asof or datetime.now()
    n_studies = len({r["topic"] for r in rows})
    dates = sorted({s["date"] for s in studies})
    n_rec = sum(1 for r in rows if r.get("base_src") == "記錄")
    with_control = control_n > 0 and any(r.get("e_h5") is not None or r.get("e_latest") is not None for r in rows)
    lines = [f"# 研究成績單（{asof:%Y-%m-%d} 產生）", "",
             f"研究 {len(studies)} 篇（日期 {dates[0] if dates else '—'}～{dates[-1] if dates else '—'}），有價格資料的 {n_studies} 篇、{len(rows)} 個（研究, 個股）組合。",
             "超額報酬 ＝ 個股報酬 − 同期間加權指數報酬。基準價：研究發布當下記錄的價格"
             f"（{n_rec} 列；從這個功能上線之後的研究才有），其餘用研究日（含）前最後一個收盤。", ""]
    if with_control:
        lines += [f"對等權重對照組：沒被研究點名的上市櫃一般股票隨機 {control_n} 檔（固定種子，每次同一批）、同期間等權重平均報酬；"
                  "「對等權重超額」＝ 個股報酬 − 對照組報酬，看研究股有沒有贏過普通股票。", ""]
    lines += ["> **怎麼讀：先看限制。** 研究多半是在「資金已經流入、股價已經動了」之後才排進佇列，所以這不是隨機股票的對照；"
              "樣本期間只有幾週、窗口彼此重疊、同一檔會出現在多篇研究、沒有算交易成本；對照組也沒排除當時的熱門股。"
              f"只能當「哪類研究值得多花力氣」的初步線索，不能當績效。樣本少於 {MIN_N} 的分組標 ⚠，別拿來下結論。", ""]
    for horizon, label in (("h5", "5 個交易日"), ("h10", "10 個交易日"), ("h20", "20 個交易日"),
                           ("latest", "到最新收盤（天數不一）")):
        lines += [f"## {label}超額報酬", ""]
        for key, name in GROUPS:
            lines += _table(key, rows, horizon, name, with_control)
    return "\n".join(lines).rstrip() + "\n"
