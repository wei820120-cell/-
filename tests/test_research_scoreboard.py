"""研究成績單（market_intel/analysis/research_scoreboard.py）：用合成價格驗證基準日、期間報酬、超額報酬與分組統計。"""
from __future__ import annotations

import json

import pandas as pd

from market_intel.analysis import research_scoreboard as sb


def series(start: str, values: list[float], tz: bool = True) -> pd.Series:
    """每個交易日（只含平日）一筆收盤；tz=True 模擬 Yahoo 的 UTC 時間戳（台股 09:00 ＝ 01:00 UTC）。"""
    days = pd.bdate_range(start, periods=len(values))
    idx = (days + pd.Timedelta(hours=1)).tz_localize("UTC") if tz else days
    return pd.Series(values, index=idx)


def test_study_type_by_topic_name():
    assert sb.study_type("供需事件：輝達客戶Megaspeed") == "供需事件"
    assert sb.study_type("宏碁（2353）題材與產業") == "個股題材"
    assert sb.study_type("被動元件") == "產業題材"


def test_forward_returns_use_last_close_on_or_before_research_date():
    s = series("2026-10-01", [100, 101, 102, 103, 104, 110, 111, 112, 113, 114, 115, 120])   # 10/1(四)起每個平日
    fr = sb.forward_returns(s, "2026-10-05")           # 研究日當天（週一，第 3 個交易日 = 102）→ 基準 102
    assert fr["base"] == 102
    assert round(fr["h5"], 2) == round((112 / 102 - 1) * 100, 2)       # 之後第 5 個交易日
    assert "h20" not in fr                                              # 資料不夠長就不放
    assert fr["latest_days"] == 9 and round(fr["latest"], 2) == round((120 / 102 - 1) * 100, 2)
    fr_weekend = sb.forward_returns(s, "2026-10-04")   # 週日 → 用前一個交易日（10/2 = 101）
    assert fr_weekend["base"] == 101
    assert sb.forward_returns(s, "2026-09-01") == {}   # 研究日之前沒有任何資料 → 空
    assert sb.forward_returns(pd.Series(dtype=float), "2026-10-05") == {}


def test_forward_returns_handles_tz_naive_index():
    s = series("2026-10-01", [100, 110, 121], tz=False)
    assert round(sb.forward_returns(s, "2026-10-01")["latest"], 2) == 21.0


def test_rows_excess_return_against_benchmark():
    studies = [{"topic": "供需事件：甲", "type": "供需事件", "status": "混合", "date": "2026-10-01",
                "picks": {"1111": "受惠", "2222": "受傷", "9999": "中性"}}]
    prices = {"1111": series("2026-10-01", [100, 102, 104, 106, 108, 110, 112]),
              "2222": series("2026-10-01", [100, 99, 98, 97, 96, 95, 94])}      # 9999 沒價格 → 略過
    bench = series("2026-10-01", [100, 101, 102, 103, 104, 105, 106])
    rows = sb.build_rows(studies, prices, bench)
    assert {r["code"] for r in rows} == {"1111", "2222"}
    a = next(r for r in rows if r["code"] == "1111")
    assert round(a["h5"], 1) == 10.0 and round(a["x_h5"], 1) == 5.0         # 110/100 − 105/100
    b = next(r for r in rows if r["code"] == "2222")
    assert b["x_h5"] < 0 and b["impact"] == "受傷"
    assert sb.build_rows(studies, prices, None)[0]["x_h5"] is None           # 沒大盤 → 超額 None，不崩


def test_aggregate_groups_and_hit_rate():
    rows = [{"type": "供需事件", "code": "1", "x_h5": 4.0}, {"type": "供需事件", "code": "2", "x_h5": -2.0},
            {"type": "供需事件", "code": "1", "x_h5": 6.0}, {"type": "個股題材", "code": "3", "x_h5": 1.0},
            {"type": "個股題材", "code": "4", "x_h5": None}]
    agg = {a["group"]: a for a in sb.aggregate(rows, "type", "x_h5")}
    assert agg["供需事件"]["n"] == 3 and agg["供需事件"]["codes"] == 2
    assert round(agg["供需事件"]["mean"], 2) == 2.67 and agg["供需事件"]["median"] == 4.0 and round(agg["供需事件"]["hit"]) == 67
    assert agg["個股題材"]["n"] == 1                                          # None 不算樣本


def test_load_studies_reads_index_and_layer_impacts(tmp_path):
    (tmp_path / "research" / "data").mkdir(parents=True)
    (tmp_path / "research" / "index.json").write_text(json.dumps({
        "供需事件：甲": {"date": "2026-11-01", "status": "混合", "codes": ["1111", "2222"]},
        "乙": {"date": "2026-11-02", "status": "傳聞", "codes": ["3333"]},
        "沒日期": {"status": "混合", "codes": ["4444"]}}), encoding="utf-8")
    (tmp_path / "research" / "data" / "供需事件：甲.json").write_text(json.dumps({"layers": [
        {"tw_stocks": [{"code": "1111", "impact": "受惠"}, {"code": "2222", "impact": "受傷"}]},
        {"tw_stocks": [{"code": "1111", "impact": "中性"}]}]}), encoding="utf-8")       # 重複的代號取第一次的標註
    st = {s["topic"]: s for s in sb.load_studies(tmp_path)}
    assert st["供需事件：甲"]["picks"] == {"1111": "受惠", "2222": "受傷"} and st["供需事件：甲"]["type"] == "供需事件"
    assert st["乙"]["picks"] == {"3333": "未標註"}                                         # 沒有 data 檔：用索引代號
    assert "沒日期" not in st
    assert sb.load_studies(tmp_path / "不存在") == []


def test_render_contains_limits_and_tables():
    studies = [{"topic": "供需事件：甲", "type": "供需事件", "status": "混合", "date": "2026-10-01", "picks": {"1111": "受惠"}}]
    prices = {"1111": series("2026-10-01", [100, 102, 104, 106, 108, 110, 112])}
    bench = series("2026-10-01", [100, 101, 102, 103, 104, 105, 106])
    md = sb.render(sb.build_rows(studies, prices, bench), studies)
    assert "怎麼讀：先看限制" in md and "不是隨機股票的對照" in md
    assert "| 供需事件 | 1 | 1 | +5.0% | +5.0% | 100% |" in md and "依個股方向標註" in md
