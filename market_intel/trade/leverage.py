"""槓桿階梯與自我檢查（提醒用，不下單）：把巨人傑的動態槓桿做法寫成規則（筆記 knowledge/methods/巨人傑-盤勢操作與槓桿.md）。

他自己說的做法（2026-11-13 貼文）：
- 槓桿是動態、隨時可調的工具；行情不好、開始賠錢時**快速降**，並保持「最壞情況下可以一次把融資全數現償、轉成零槓桿現股」的狀態；
- 重新**試探**加槓只在兩個時點：開盤全面跌停覺得機會來了、或大盤明顯回穩；判斷錯就立刻退回低槓桿；
- 看對了、**未實現獲利拉開**，才依信心慢慢加（擴張）。

這裡的對應（數字都是**暫定值**，settings.yaml 的 leverage，沒有實績可校準；我們沒有使用者的融資部位資料，只對實單記帳 state/trade/real.json 的股票期貨部位算）：
- 防守：市場「恐慌」，或帳戶距歷史高點回落 ≥ drawdown_defense_pct% → 上限 base × defense_mult
- 試探：市場「回穩」（且不在回落門檻內）→ 上限 base × probe_mult
- 擴張：市場正常或回穩，且累積獲利 ≥ profit_expand_pct%、沒有在回落 → 上限 base × expand_mult
- 其他（含「警戒」）：標準，上限 base（警戒時不擴張）
槓桿倍數 ＝ 持倉名目價值 ÷ 權益。另做壓力測試：全部持倉一次跌 gap_pct%（≈跌停）的虧損占權益幾 %。
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import config
from ..utils import ROOT

STATE_PATH = ROOT / "state" / "trade" / "leverage.json"
DEFAULTS = {"enabled": True, "base": 1.0, "defense_mult": 0.5, "probe_mult": 0.75, "expand_mult": 1.5,
            "drawdown_defense_pct": 10.0, "profit_expand_pct": 10.0, "gap_pct": 10.0}


def settings() -> dict:
    return {**DEFAULTS, **((config.settings().get("leverage") or {}))}


def exposure(positions: list[dict], closes: dict[str, float], equity: float) -> tuple[float, float]:
    """（名目價值, 槓桿倍數）。沒有今天收盤價的持倉用進場價。"""
    notional = sum(float(p["qty"]) * float(p["mult"]) * float(closes.get(p["code"]) or p["entry"]) for p in positions)
    return notional, (notional / equity if equity > 0 else 0.0)


def ladder(equity: float, capital: float, peak: float, stress_level: str, cfg: dict | None = None) -> dict:
    """回傳 {"level", "cap", "reasons", "dd_pct", "profit_pct"}。"""
    cfg = cfg or settings()
    dd = (peak - equity) / peak * 100 if peak > 0 else 0.0
    profit = (equity / capital - 1) * 100 if capital > 0 else 0.0
    base = float(cfg["base"])
    in_dd = dd >= float(cfg["drawdown_defense_pct"])
    if stress_level == "恐慌" or in_dd:
        why = ["市場恐慌（流動性風險）"] if stress_level == "恐慌" else []
        if in_dd:
            why.append(f"帳戶距高點回落 {dd:.1f}%（≥ {cfg['drawdown_defense_pct']}%）：賠錢時要快速降")
        return {"level": "防守", "cap": base * float(cfg["defense_mult"]), "reasons": why, "dd_pct": dd, "profit_pct": profit}
    if stress_level == "回穩":
        return {"level": "試探", "cap": base * float(cfg["probe_mult"]), "dd_pct": dd, "profit_pct": profit,
                "reasons": ["恐慌後回穩：可以開始試探加槓；判斷錯就立刻退回低槓桿"]}
    if stress_level == "正常" and profit >= float(cfg["profit_expand_pct"]):
        return {"level": "擴張", "cap": base * float(cfg["expand_mult"]), "dd_pct": dd, "profit_pct": profit,
                "reasons": [f"累積獲利 {profit:.1f}%（≥ {cfg['profit_expand_pct']}%）、市場正常：未實現獲利拉開才慢慢加"]}
    why = ["市場警戒：不擴張"] if stress_level == "警戒" else []
    return {"level": "標準", "cap": base, "reasons": why, "dd_pct": dd, "profit_pct": profit}


def load(path: Path | None = None) -> dict:
    try:
        d = json.loads((path or STATE_PATH).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def update_peak(equity: float, capital: float, path: Path | None = None) -> float:
    """帳戶權益的歷史高點（至少是本金），存檔。"""
    path = path or STATE_PATH
    st = load(path)
    peak = max(float(st.get("peak") or 0), float(equity), float(capital))
    st["peak"] = round(peak, 2)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(st, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return peak


def text(lad: dict, equity: float, notional: float, lev: float, cfg: dict | None = None) -> str:
    cfg = cfg or settings()
    gap = float(cfg["gap_pct"])
    loss = notional * gap / 100
    lines = ["🧭 槓桿檢查（提醒用、不下單；上限是暫定值）",
             f"　階梯：{lad['level']}｜建議槓桿上限 {lad['cap']:.2f} 倍｜目前 {lev:.2f} 倍（持倉名目 {notional:,.0f}／權益 {equity:,.0f}）",
             f"　帳戶：累積 {lad['profit_pct']:+.1f}%、距高點回落 {lad['dd_pct']:.1f}%"]
    lines += [f"　・{x}" for x in lad.get("reasons", [])]
    if lev > lad["cap"] + 1e-9:
        lines.append(f"　⚠️ 目前 {lev:.2f} 倍超過{lad['level']}上限 {lad['cap']:.2f} 倍：照他的做法應先降槓桿。")
    pct = loss / equity * 100 if equity > 0 else 0.0
    lines.append(f"　壓力測試：全部持倉一次跌 {gap:g}%（≈跌停）虧損約 {loss:,.0f} 元，占權益 {pct:.1f}%"
                 f"{'；最壞情況下無法一次現償' if loss >= equity else '；最壞情況下仍可全數現償'}。")
    return "\n".join(lines)
