"""市場流動性指標、槓桿階梯、恐慌日研究清單（analysis/market_stress.py、trade/leverage.py、analysis/panic_watch.py）。"""
from __future__ import annotations

import json

import pandas as pd

from market_intel.analysis import market_stress as ms
from market_intel.analysis import panic_watch as pw
from market_intel.trade import leverage as lv

CFG = dict(ms.DEFAULTS)


def day_df(rows):
    """rows: (code, close, change, volume, value)。"""
    return pd.DataFrame([{"code": c, "close": cl, "change": ch, "volume": v, "value": val} for c, cl, ch, v, val in rows])


def test_day_stats_counts_limit_moves_and_skips_etf_warrants_and_zero_volume():
    df = day_df([("2330", 90.0, -10.0, 1000, 9e8),          # -10% 跌停
                 ("2317", 99.0, -1.0, 1000, 5e8),           # 小跌
                 ("2454", 110.0, 10.0, 1000, 4e8),          # +10% 漲停
                 ("1101", 50.0, 0.0, 1000, 1e8),            # 平盤
                 ("0050", 150.0, -15.0, 1000, 8e8),         # ETF（0 開頭）略過
                 ("031234", 1.0, -0.2, 1000, 1e6),          # 權證（6 碼）略過
                 ("9999", 10.0, -1.0, 0, 0)])               # 沒成交略過
    s = ms.day_stats(df, CFG)
    assert (s["n"], s["ld"], s["lu"], s["up"], s["down"]) == (4, 1, 1, 1, 2)
    assert s["value"] == 9e8 + 5e8 + 4e8 + 1e8
    assert ms.day_stats(pd.DataFrame(columns=["code"]), CFG)["n"] == 0


def _s(ld=0, lu=0, up=500, down=500, value=1e11):
    return {"n": 1500, "ld": ld, "lu": lu, "up": up, "down": down, "value": value}


def test_classify_panic_warn_thin_recover_normal():
    prev = [{"d": f"2026-11-{i:02d}", **_s(value=1e11), "level": "正常"} for i in range(1, 8)]
    assert ms.classify(prev, _s(ld=120), CFG)[0] == "恐慌"
    assert ms.classify(prev, _s(ld=35), CFG)[0] == "警戒"
    lvl, why = ms.classify(prev, _s(up=300, down=900, value=0.7e11), CFG)           # 量縮下跌：0.7 倍、下跌多於上漲
    assert lvl == "警戒" and "量縮下跌" in why[0]
    assert ms.classify(prev, _s(up=900, down=300, value=0.7e11), CFG)[0] == "正常"      # 量縮但上漲多：不算
    assert ms.classify(prev, _s(ld=3), CFG)[0] == "正常"
    after = prev + [{"d": "2026-11-08", **_s(ld=150), "level": "恐慌"}]
    lvl, why = ms.classify(after, _s(ld=4, up=800, down=400), CFG)
    assert lvl == "回穩" and "恐慌或警戒" in why[0]
    assert ms.classify(after, _s(ld=4, up=300, down=900), CFG)[0] == "正常"             # 還在跌：不算回穩
    assert ms.classify([], _s(up=300, down=900, value=0.1e11), CFG)[0] == "正常"        # 沒有歷史就不判量縮


def test_record_persists_overwrites_same_day_and_chains_levels(tmp_path):
    p = tmp_path / "ms.json"
    ms.record("2026-11-05", _s(ld=2), p, CFG)
    r = ms.record("2026-11-06", _s(ld=130), p, CFG)
    assert r["level"] == "恐慌" and [x["d"] for x in ms.load(p)] == ["2026-11-05", "2026-11-06"]
    r2 = ms.record("2026-11-09", _s(ld=5, up=900, down=300), p, CFG)
    assert r2["level"] == "回穩"
    r3 = ms.record("2026-11-09", _s(ld=60), p, CFG)                                    # 同一天重跑：覆蓋
    assert r3["level"] == "警戒" and len(ms.load(p)) == 3
    assert "市場流動性：警戒" in ms.text(r3) and "跌停 60 家" in ms.text(r3)


def test_ladder_defense_probe_expand_standard():
    c = dict(lv.DEFAULTS)
    d = lv.ladder(100_000, 100_000, 100_000, "恐慌", c)
    assert d["level"] == "防守" and d["cap"] == 0.5
    d = lv.ladder(88_000, 100_000, 100_000, "正常", c)                                   # 回落 12% ≥ 10%
    assert d["level"] == "防守" and any("回落" in x for x in d["reasons"])
    d = lv.ladder(100_000, 100_000, 100_000, "回穩", c)
    assert d["level"] == "試探" and d["cap"] == 0.75
    d = lv.ladder(112_000, 100_000, 112_000, "正常", c)                                  # 累積 +12%、沒回落
    assert d["level"] == "擴張" and d["cap"] == 1.5
    d = lv.ladder(112_000, 100_000, 112_000, "警戒", c)                                  # 警戒不擴張
    assert d["level"] == "標準" and d["cap"] == 1.0 and "不擴張" in d["reasons"][0]
    d = lv.ladder(112_000, 100_000, 112_000, "回穩", c)                                  # 回穩先是試探，不直接擴張
    assert d["level"] == "試探"


def test_exposure_stress_test_and_peak(tmp_path):
    pos = [{"code": "2330", "qty": 2, "mult": 2000, "entry": 100.0}, {"code": "2317", "qty": 1, "mult": 2000, "entry": 50.0}]
    notional, lev = lv.exposure(pos, {"2330": 110.0}, 100_000)             # 2317 沒收盤價 → 用進場價
    assert notional == 2 * 2000 * 110 + 1 * 2000 * 50 and round(lev, 2) == 5.4
    lad = lv.ladder(50_000, 50_000, 50_000, "正常", dict(lv.DEFAULTS))
    n2, lev2 = lv.exposure(pos, {"2330": 110.0}, 50_000)
    t = lv.text(lad, 50_000, n2, lev2, dict(lv.DEFAULTS))                    # 名目 54 萬、權益 5 萬：跌 10% 虧 5.4 萬 ≥ 權益
    assert "超過標準上限" in t and "壓力測試" in t and "無法一次現償" in t
    t_ok = lv.text(lad, 100_000, notional, lev, dict(lv.DEFAULTS))           # 權益 10 萬：虧 5.4 萬 < 權益
    assert "仍可全數現償" in t_ok
    p = tmp_path / "lev.json"
    assert lv.update_peak(90_000, 100_000, p) == 100_000 and lv.update_peak(120_000, 100_000, p) == 120_000
    assert lv.update_peak(95_000, 100_000, p) == 120_000                    # 高點不會往下改
    assert json.loads(p.read_text())["peak"] == 120000.0


def series(start, values):
    return pd.Series(values, index=(pd.bdate_range(start, periods=len(values)) + pd.Timedelta(hours=1)).tz_localize("UTC"))


def test_panic_watch_candidates_filter_merge_and_render(tmp_path):
    studies = [{"topic": "供需事件：甲", "type": "供需事件", "status": "混合", "date": "2026-10-05", "picks": {"1111": "受惠", "2222": "受惠", "3333": "受傷"}},
               {"topic": "乙", "type": "產業題材", "status": "混合", "date": "2026-10-12", "picks": {"1111": "受惠"}}]
    prices = {"1111": series("2026-10-01", [100, 100, 100, 110, 112, 110, 100, 95, 92, 90]),     # 相對研究日 -10%、相對高點 -19.6% → 入列
              "2222": series("2026-10-01", [100, 100, 100, 101, 102, 103, 104, 105, 106, 107]),  # 沒回落
              "3333": series("2026-10-01", [100, 100, 100, 90, 80, 70, 60, 60, 60, 60])}          # 受傷：不列
    details = {"供需事件：甲": {"catalysts": ["月營收"], "risks": ["客戶砍單"]}, "乙": {"catalysts": [], "risks": ["報價下滑"]}}
    rows = pw.candidates(studies, prices, details, {"1111": "甲公司"}, drop_pct=12)
    assert [r["code"] for r in rows] == ["1111"] and rows[0]["name"] == "甲公司" and len(rows[0]["topics"]) == 2
    assert rows[0]["dd"] < -19 and round(rows[0]["since"]) == -10
    md = pw.render(rows, "恐慌", "2026-11-13", 12)
    assert "不是買進建議" in md and "1111" in md and "客戶砍單" in md and "報價下滑" in md and "市場流動性狀態：**恐慌**" in md
    assert "沒有符合條件" in pw.render([], None, "2026-11-13")
    (tmp_path / "research" / "data").mkdir(parents=True)
    (tmp_path / "research" / "data" / "乙.json").write_text(json.dumps({"catalysts": ["a", "b", "c", "d"], "risks": ["r"]}), encoding="utf-8")
    det = pw.load_details(tmp_path, ["乙", "不存在"])
    assert det["乙"]["catalysts"] == ["a", "b", "c"] and det["不存在"] == {"catalysts": [], "risks": []}


def test_post_close_section_combines_stress_and_leverage_and_never_raises(tmp_path, monkeypatch):
    from market_intel import cli
    monkeypatch.setattr(ms, "STATE_PATH", tmp_path / "ms.json")
    monkeypatch.setattr(lv, "STATE_PATH", tmp_path / "lev.json")
    rows = [(f"{1000 + i}", 90.0, -10.0, 1000, 1e8) for i in range(120)] + [(f"{2000 + i}", 100.0, 1.0, 1000, 1e8) for i in range(300)]
    monkeypatch.setattr(cli.tw_daily, "fetch_day_all", lambda: day_df(rows))
    rst = {"equity": 100_000.0, "capital": 100_000.0, "positions": [{"code": "2330", "qty": 1, "mult": 2000, "entry": 100.0}]}
    out = cli._market_stress_section(rst, {"2330": 100.0}, "2026-11-06")
    assert "市場流動性：恐慌" in out and "跌停 120 家" in out and "階梯：防守" in out and "超過防守上限" in out     # 槓桿 2 倍 > 0.5
    monkeypatch.setattr(cli.tw_daily, "fetch_day_all", lambda: (_ for _ in ()).throw(RuntimeError("網路失敗")))
    assert cli._market_stress_section(rst, {}, "2026-11-09") == ""                                                  # 抓不到資料：不丟例外
