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


def test_impact_class_groups_free_text_by_leading_label():
    assert sb.impact_class("受惠") == "受惠" and sb.impact_class("受惠，毛利率創高") == "受惠" and sb.impact_class("受惠（傳聞）") == "受惠"
    assert sb.impact_class("受傷") == "受傷" and sb.impact_class("中性偏負") == "中性" and sb.impact_class("混合") == "混合"
    assert sb.impact_class("同業，另案研究") == "其他" and sb.impact_class("間接") == "其他"      # 開頭不是四個標籤就歸其他，不猜
    assert sb.impact_class("") == "未標註" and sb.impact_class(None) == "未標註" and sb.impact_class("未標註") == "未標註"


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
        {"tw_stocks": [{"code": "1111", "impact": "受惠，毛利率創高"}, {"code": "2222", "impact": "受傷"}]},
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
    assert "| 供需事件 ⚠樣本少 | 1 | 1 | +5.0%｜100% | +5.0% |" in md and "依個股方向標註" in md      # 樣本少於 MIN_N 標 ⚠
    assert "| **全部** ⚠樣本少 | 1 | 1 | +5.0%｜100% | +5.0% |" in md
    assert "依觸發來源" in md and "依證據等級" in md and "對等權重對照組" not in md       # 沒有對照組時不印對照欄


def test_trigger_type_classifies_by_leading_text():
    assert sb.trigger_type("2026-10-03 🔥 盤後資金流入：量比 2.43、資金 +212.2 億（Claude 代為研究）") == "資金流入"
    assert sb.trigger_type("2026-10-23 連動預研：MLCC供需 研究完成，相關個股先研究起來") == "連動預研"
    assert sb.trigger_type("2026-10-27 早期訊號（未證實，來源：Google新聞") == "早期訊號（未證實新聞）"
    assert sb.trigger_type("2026-11-14 供需失衡（原料短缺）：美中稀土") == "供需新聞"
    assert sb.trigger_type("Threads @abc 貼文 https://www.threads.com/@abc/post/x，未證實") == "社群／Podcast"
    assert sb.trigger_type("股癌 EP700 12:30 提到某某公司") == "社群／Podcast"
    assert sb.trigger_type("手動指定") == "手動" and sb.trigger_type("") == "未記錄" and sb.trigger_type("某種新格式") == "其他／未記錄"
    assert sb.trigger_type("2026-11-10 使用者詢問：高明鐵為什麼沒有被研究到（不在任何族群的強勢股）") == "手動"            # 使用者詢問優先於內文提到的強勢股
    assert sb.trigger_type("2026-11-05 不在任何族群的強勢股：5222 中華化｜漲停 +9.8%、成交量放大") == "強勢股（股價先動）"
    assert sb.trigger_type("2026-11-02 重大事件：沙特領銜OPEC+增產") == "重大事件新聞"
    assert sb.trigger_type("頻道貼文偵測（重要性 4）：ASML Q3營收創高") == "社群／Podcast"
    assert sb.trigger_type("經濟部 115/10/3 公告（經貿字第1150000號）：自即日起中國") == "官方公告"


def test_forward_returns_entry_price_replaces_base():
    s = series("2026-10-01", [100, 102, 104, 106, 108, 110, 112])
    assert sb.forward_returns(s, "2026-10-01")["base"] == 100
    fr = sb.forward_returns(s, "2026-10-01", entry=102)          # 發布當下價 102（研究日盤中），第 5 天收 110
    assert fr["base"] == 102 and round(fr["h5"], 2) == round((110 / 102 - 1) * 100, 2)
    assert sb.forward_returns(s, "2026-10-01", entry=0)["base"] == 100          # 價格 0／None 不用


def test_build_rows_uses_recorded_entry_and_flags_source():
    studies = [{"topic": "甲", "type": "產業題材", "status": "混合", "date": "2026-10-01", "picks": {"1111": "受惠", "2222": "受惠"},
                "trigger_type": "資金流入", "evidence": "媒體報導",
                "entry": {"asof": "2026-10-01T10:00:00+08:00", "bench": 100.0, "px": {"1111": 102.0}}}]      # 只有 1111 有記錄價
    prices = {"1111": series("2026-10-01", [100, 102, 104, 106, 108, 110, 112]),
              "2222": series("2026-10-01", [100, 102, 104, 106, 108, 110, 112])}
    bench = series("2026-10-01", [100, 101, 102, 103, 104, 105, 106])
    rows = {r["code"]: r for r in sb.build_rows(studies, prices, bench)}
    assert rows["1111"]["base_src"] == "記錄" and round(rows["1111"]["h5"], 2) == round((110 / 102 - 1) * 100, 2)
    assert rows["2222"]["base_src"] == "收盤" and round(rows["2222"]["h5"], 1) == 10.0
    assert rows["1111"]["trigger_type"] == "資金流入" and rows["1111"]["evidence"] == "媒體報導"


def test_control_group_excess_and_minimum_stock_count():
    flat = {f"c{i}": series("2026-10-01", [100, 100, 100, 100, 100, 102, 102]) for i in range(25)}     # 25 檔對照組：5 日後 +2%
    assert round(sb.control_returns(flat, "2026-10-01")["h5"], 2) == 2.0
    assert sb.control_returns({k: flat[k] for k in list(flat)[:5]}, "2026-10-01") == {}                # 太少檔：不算
    studies = [{"topic": "甲", "type": "產業題材", "status": "混合", "date": "2026-10-01", "picks": {"1111": "受惠"}}]
    prices = {"1111": series("2026-10-01", [100, 102, 104, 106, 108, 110, 112])}
    bench = series("2026-10-01", [100, 101, 102, 103, 104, 105, 106])
    r = sb.build_rows(studies, prices, bench, control=flat)[0]
    assert round(r["x_h5"], 1) == 5.0 and round(r["e_h5"], 1) == 8.0                                   # 10% − 對照組 2%
    assert sb.build_rows(studies, prices, bench)[0]["e_h5"] is None                                    # 沒給對照組 → None
    md = sb.render([r], studies, control_n=25)
    assert "對等權重對照組：平均超額｜勝率" in md and "+8.0%｜100%" in md


def test_pick_control_is_stable_excludes_research_and_filters_codes():
    listings = {f"{1000 + i}": {"market": "tse" if i % 2 else "otc"} for i in range(300)}
    listings["0050"] = {"market": "tse"}; listings["2330A"] = {"market": "tse"}; listings["9999"] = {"market": "emerging"}
    a = sb.pick_control(listings, {"1001", "1002"}, n=50)
    assert a == sb.pick_control(listings, {"1001", "1002"}, n=50) and len(a) == 50                       # 同種子同一批
    assert not {"1001", "1002", "0050", "2330A", "9999"} & set(a)
    assert sb.pick_control({"1111": {"market": "tse"}}, set(), n=50) == ["1111"]                      # 不夠就全取


def test_load_studies_reads_trigger_evidence_and_entry(tmp_path):
    (tmp_path / "research" / "data").mkdir(parents=True)
    (tmp_path / "research" / "2026-11-01-甲.md").write_text(
        "# x\n\n<details><summary>觸發來源</summary>\n\n2026-11-01 🔥 盤後資金流入：量比 2\n\n</details>\n", encoding="utf-8")
    (tmp_path / "research" / "index.json").write_text(json.dumps({
        "甲": {"file": "2026-11-01-甲.md", "date": "2026-11-01", "status": "混合", "codes": ["1111"], "evidence": "官方公告"},
        "乙": {"file": "不存在.md", "date": "2026-11-02", "status": "混合", "codes": ["2222"]}}), encoding="utf-8")
    (tmp_path / "research" / "entry_prices.json").write_text(json.dumps({
        "甲": {"asof": "2026-11-01T10:05:00+08:00", "bench": 25000.0, "px": {"1111": 55.5}},
        "乙": {"asof": "2026-10-20T10:05:00+08:00", "bench": 24000.0, "px": {"2222": 10.0}}}), encoding="utf-8")   # 日期對不上：不用
    st = {s["topic"]: s for s in sb.load_studies(tmp_path)}
    assert st["甲"]["trigger_type"] == "資金流入" and st["甲"]["evidence"] == "官方公告" and st["甲"]["entry"]["px"] == {"1111": 55.5}
    assert st["乙"]["trigger_type"] == "未記錄" and st["乙"]["evidence"] == "未標註" and st["乙"]["entry"] is None


def test_record_entry_prices_writes_latest_close_and_bench(tmp_path, monkeypatch):
    from market_intel import research
    monkeypatch.setattr(research, "ENTRY_PATH", tmp_path / "research" / "entry_prices.json")
    layers = [{"layer": "甲", "tw_stocks": [{"code": "1111", "name": "甲"}, {"code": "2222", "name": "乙"}, {"code": "3333", "name": "丙"}]}]
    listings = {"1111": {"market": "tse"}, "2222": {"market": "otc"}}

    def fake(syms):
        assert "1111.TW" in syms and "2222.TWO" in syms and "^TWII" in syms
        mk = lambda v: pd.DataFrame({"close": v})
        return {"1111.TW": mk([50.0, 51.234]), "2222.TWO": mk([10.0, None]), "^TWII": mk([25000.0, 25100.5])}       # 3333 沒價格 → 略過

    rec = research.record_entry_prices("題材甲", layers, listings, fetch=fake)
    assert rec["px"] == {"1111": 51.23, "2222": 10.0} and rec["bench"] == 25100.5
    rec2 = research.record_entry_prices("題材乙", layers, listings, fetch=fake)                                    # 第二個題材：保留第一個
    saved = json.loads((tmp_path / "research" / "entry_prices.json").read_text(encoding="utf-8"))
    assert set(saved) == {"題材甲", "題材乙"} and saved["題材甲"]["px"]["1111"] == 51.23
    assert research.record_entry_prices("丁", [], listings, fetch=fake) is None                                     # 沒個股
    assert research.record_entry_prices("戊", layers, listings, fetch=lambda s: {}) is None                         # 全部抓不到 → 不寫

    def boom(syms):
        raise RuntimeError("Yahoo 掛了")
    assert research.record_entry_prices("己", layers, listings, fetch=boom) is None                                 # 例外不外洩


def test_save_report_keeps_valid_evidence_only(tmp_path, monkeypatch):
    from market_intel import ai, research
    monkeypatch.setattr(research, "RESEARCH_DIR", tmp_path / "research")
    monkeypatch.setattr(research, "INDEX_PATH", tmp_path / "research" / "index.json")
    monkeypatch.setattr(research, "AUTO_THEMES_PATH", tmp_path / "research" / "auto_themes.yaml")
    monkeypatch.setattr(research, "QUEUE_DIR", tmp_path / "queue")
    assert research.EVIDENCE_LEVELS == ("官方公告", "數據報告", "媒體報導", "社群傳聞")
    assert research.REPORT_SCHEMA["properties"]["evidence"]["enum"] == list(research.EVIDENCE_LEVELS)
    assert "evidence" not in research.REPORT_SCHEMA["required"]          # 選填：舊流程不用改
    base = {"one_line": "x", "status": "混合", "horizon": "中期（3-12個月）", "keywords": [], "catalysts": [], "risks": [],
            "spec_tables": [], "evolution": [], "concepts": [], "conclusion": [], "sources": [], "layers": []}
    research._save_report("甲", {**base, "topic": "甲", "evidence": "官方公告"}, "報告", "觸發", {}, {}, ai.Usage(), False)
    research._save_report("乙", {**base, "topic": "乙", "evidence": "我亂寫的"}, "報告", "觸發", {}, {}, ai.Usage(), False)
    research._save_report("丙", {**base, "topic": "丙"}, "報告", "觸發", {}, {}, ai.Usage(), False)
    idx = research.load_index()
    assert idx["甲"]["evidence"] == "官方公告" and "evidence" not in idx["乙"] and "evidence" not in idx["丙"]     # 不在清單內的值不收
    d = lambda t: json.loads((tmp_path / "research" / "data" / f"{research.slug(t)}.json").read_text(encoding="utf-8"))
    assert d("甲")["evidence"] == "官方公告" and "evidence" not in d("乙")
