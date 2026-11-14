"""系統健康日報：每天早上一則推播，說明昨天各排程有沒有跑、有沒有失敗、資料是不是過期、夜盤有沒有中斷。

為什麼要有：這個系統靠 GitHub Actions 排程，排程會延遲、漏跑，程式也會悄悄壞掉（例如盤後報告的測試壞了連續多天失敗、夜盤午夜卡住），
以前都是事後才發現。這裡只做「檢查與回報」，不修任何東西。

檢查項目（每項回傳 {"level": ok／warn／bad, "name": 名稱, "note": 說明}）：
- 各 workflow：最新一次執行有沒有失敗、該跑的那天有沒有跑（平日型）、監看常駐是否還在跑（常駐型）、過去 24 小時失敗幾次
- 資料新鮮度：市場流動性紀錄是否落後、研究佇列有沒有題材等太久沒研究、main 最近一次 commit 距今多久（監看有在存檔）
- 期貨日盤／夜盤報價有沒有中斷（相鄰兩筆報價間隔超過 20 分鐘）

台灣休市日（平日但沒開盤）會讓「市場流動性落後」之類的檢查多報一次，說明裡有提醒。
只是監控回報，不是投資建議。
"""
from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from .utils import TW_TZ

log = logging.getLogger(__name__)

# 預設要檢查的 workflow（可在 config/settings.yaml 的 health.workflows 覆蓋）。
#   kind=interval：常駐／固定間隔，最新一次執行距今不能超過 max_age_h（有正在跑的就算正常）
#   kind=weekday ：平日型，上一個平日必須有執行（GitHub 排程常延遲到半夜，所以看台北日期，不看幾點）
DEFAULT_WORKFLOWS = [
    {"name": "watch", "label": "常駐監看", "kind": "interval", "max_age_h": 3},
    {"name": "podcast", "label": "Podcast", "kind": "interval", "max_age_h": 8},
    {"name": "realtime", "label": "日盤即時", "kind": "weekday"},
    {"name": "realtime-night", "label": "夜盤", "kind": "weekday"},
    {"name": "daily-report", "label": "盤後報告", "kind": "weekday"},
]

GAP_MIN = 20          # 報價相鄰兩筆間隔超過這麼多分鐘算中斷
LEVEL_ICON = {"ok": "✅", "warn": "⚠️", "bad": "❌"}


def _ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(TW_TZ)
    except ValueError:
        return None


def prev_weekday(now: datetime) -> datetime:
    """嚴格早於今天的最近一個平日（週一→上週五）。"""
    d = now.date() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return datetime(d.year, d.month, d.day, tzinfo=TW_TZ)


def check_workflow(spec: dict, runs: list[dict], now: datetime) -> dict:
    """runs：該 workflow 在預設分支的最近執行（gh run list --json status,conclusion,createdAt，新到舊）。"""
    label = spec.get("label") or spec["name"]
    done = [r for r in runs if r.get("status") == "completed"]
    running = any(r.get("status") in ("in_progress", "queued") for r in runs)
    since = now - timedelta(hours=24)
    fails = [r for r in done if r.get("conclusion") == "failure" and (_ts(r.get("createdAt")) or now) >= since]
    last = done[0] if done else None
    last_at = _ts((runs[0] if runs else {}).get("createdAt"))
    problems: list[tuple[str, str]] = []
    if last and last.get("conclusion") == "failure":
        problems.append(("bad", f"最新一次執行失敗（{_ts(last.get('createdAt')):%m/%d %H:%M}）"))
    elif fails:
        problems.append(("warn", f"過去 24 小時失敗 {len(fails)} 次，最新一次已恢復"))
    if spec.get("kind") == "interval":
        age_h = (now - last_at).total_seconds() / 3600 if last_at else None
        if not running and (age_h is None or age_h > spec.get("max_age_h", 6)):
            problems.append(("bad", "沒有在跑" + (f"，距上次執行已 {age_h:.1f} 小時" if age_h is not None else "，查不到任何執行紀錄")))
    elif spec.get("kind") == "weekday":
        want = prev_weekday(now)
        lo, hi = want, want + timedelta(days=1, hours=12)          # 排程常延遲，容許延到隔天中午
        hit = [r for r in runs if (t := _ts(r.get("createdAt"))) and lo <= t < hi]
        if not hit:
            problems.append(("bad" if now >= hi else "warn", f"{want:%m/%d} 沒有執行紀錄" + ("" if now >= hi else "（可能還在延遲）")))
    if not problems:
        note = "正常" + (f"（最近 {last_at:%m/%d %H:%M}）" if last_at else "")
        return {"level": "ok", "name": label, "note": note}
    level = "bad" if any(l == "bad" for l, _ in problems) else "warn"
    return {"level": level, "name": label, "note": "；".join(n for _, n in problems)}


def check_market_stress(days: list[dict], now: datetime) -> dict:
    want = prev_weekday(now).strftime("%Y-%m-%d")
    last = days[-1]["d"] if days else None
    if last is None:
        return {"level": "warn", "name": "市場流動性紀錄", "note": "還沒有任何紀錄"}
    if last < want:
        return {"level": "warn", "name": "市場流動性紀錄", "note": f"最新一筆是 {last}，應有 {want}（若 {want[5:].replace('-', '/')} 休市可忽略）"}
    return {"level": "ok", "name": "市場流動性紀錄", "note": f"最新 {last}"}


def pending_topics(queue: list[dict], researched: set[str]) -> list[dict]:
    """佇列裡還沒有研究的題材（已在研究索引或待發布的不算）。"""
    return [q for q in queue if q.get("topic") and q["topic"] not in researched]


def check_research_queue(queue: list[dict], researched: set[str], now: datetime, max_wait_h: float = 12) -> dict:
    todo = pending_topics(queue, researched)
    if not todo:
        return {"level": "ok", "name": "研究佇列", "note": "沒有待研究題材"}
    times = [t for q in todo if (t := _parse_local(q.get("time")))]
    oldest = min(times) if times else None
    wait_h = (now - oldest).total_seconds() / 3600 if oldest else None
    note = f"{len(todo)} 題待研究" + (f"，最久已等 {wait_h:.0f} 小時" if wait_h is not None else "")
    return {"level": "warn" if wait_h is not None and wait_h > max_wait_h else "ok", "name": "研究佇列", "note": note}


def _parse_local(s: str | None) -> datetime | None:
    """佇列的 time 欄位（'2026-11-14 15:51'，台北時間）。"""
    try:
        return datetime.strptime(s or "", "%Y-%m-%d %H:%M").replace(tzinfo=TW_TZ)
    except ValueError:
        return None


def check_commit_age(last_commit: datetime | None, now: datetime, max_h: float = 3) -> dict:
    if last_commit is None:
        return {"level": "warn", "name": "監看存檔", "note": "查不到 main 最近一次 commit"}
    age_h = (now - last_commit).total_seconds() / 3600
    if age_h > max_h:
        return {"level": "bad", "name": "監看存檔", "note": f"main 已 {age_h:.1f} 小時沒有新 commit（監看可能卡住）"}
    return {"level": "ok", "name": "監看存檔", "note": f"main 最近 commit 在 {age_h * 60:.0f} 分鐘前"}


def find_gaps(ticks: list, gap_min: int = GAP_MIN) -> list[tuple[datetime, datetime]]:
    """報價序列（[[ISO 時間, 價格], ...]）中，相鄰兩筆間隔超過 gap_min 分鐘的區段。"""
    out = []
    prev = None
    for t, *_ in ticks:
        cur = _ts(t)
        if cur is None:
            continue
        if prev and (cur - prev) > timedelta(minutes=gap_min):
            out.append((prev, cur))
        prev = cur
    return out


def check_session_ticks(name: str, st: dict | None, want_date: str, end: datetime) -> dict:
    """期貨日盤／夜盤報價：該場次存在、沒有超過 GAP_MIN 的中斷、最後一筆接近收盤 end。
    存檔的場次日期比 want_date 新（新一場已經開始）就略過；比較舊或不存在就提醒。"""
    day = (st or {}).get("date", "").rstrip("N")
    if st and day > want_date:
        return {"level": "ok", "name": name, "note": f"新一場（{day}）已開始，略過 {want_date} 的檢查"}
    if not st or day != want_date:
        return {"level": "warn", "name": name, "note": f"存檔不是 {want_date} 的場次（可能休市或沒有執行）"}
    ticks = st.get("ticks") or []
    if not ticks:
        return {"level": "bad", "name": name, "note": f"{want_date} 場次沒有任何報價"}
    gaps = find_gaps(ticks)
    last = _ts(ticks[-1][0])
    notes, level = [], "ok"
    if gaps:
        level = "warn"
        shown = "、".join(f"{a:%H:%M}～{b:%H:%M}" for a, b in gaps[:3])
        notes.append(f"報價中斷 {len(gaps)} 次（{shown}）")
    if last and last < end - timedelta(minutes=15) and not st.get("finished"):
        level = "bad"
        notes.append(f"最後一筆報價在 {last:%m/%d %H:%M}，離收盤 {end:%H:%M} 還早")
    return {"level": level, "name": name, "note": "；".join(notes) if notes else f"{len(ticks)} 筆報價、最後 {last:%H:%M}"}


def render(checks: list[dict], now: datetime) -> str:
    wd = "一二三四五六日"[now.weekday()]
    bad = [c for c in checks if c["level"] == "bad"]
    warn = [c for c in checks if c["level"] == "warn"]
    ok = [c for c in checks if c["level"] == "ok"]
    head = f"🩺 系統健康日報 {now:%m/%d}（週{wd}）"
    if not bad and not warn:
        return f"{head}\n✅ {len(ok)} 項檢查全部正常"
    lines = [head, f"❌ {len(bad)} 項異常、⚠️ {len(warn)} 項注意、✅ {len(ok)} 項正常"] if bad else [head, f"⚠️ {len(warn)} 項注意、✅ {len(ok)} 項正常"]
    for c in bad + warn:
        lines.append(f"{LEVEL_ICON[c['level']]} {c['name']}：{c['note']}")
    if ok:
        lines.append("✅ 正常：" + "、".join(c["name"] for c in ok))
    return "\n".join(lines)


# ---------------------------------------------------------------- 蒐集（需要 gh 與 repo 的 checkout）

def gh_runs(workflow: str, limit: int = 20, branch: str = "main") -> list[dict]:
    """用 gh CLI 取該 workflow 在指定分支的最近執行（新到舊）。失敗回空清單（由呼叫端當「查不到」處理）。"""
    try:
        out = subprocess.run(["gh", "run", "list", "--workflow", f"{workflow}.yml", "--branch", branch, "--limit", str(limit),
                              "--json", "status,conclusion,createdAt,event"], capture_output=True, text=True, timeout=60, check=True).stdout
        return json.loads(out)
    except Exception as e:  # noqa: BLE001
        log.warning("gh run list %s 失敗：%s", workflow, e)
        return []


def last_commit_time(root: Path, ref: str = "HEAD") -> datetime | None:
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cI", ref], capture_output=True, text=True, cwd=root, timeout=30, check=True).stdout.strip()
        return _ts(out)
    except Exception as e:  # noqa: BLE001
        log.warning("git log 失敗：%s", e)
        return None


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def collect(root: Path, now: datetime, workflows: list[dict] | None = None, runs_fn=gh_runs, commit_fn=last_commit_time) -> list[dict]:
    """蒐集所有檢查。runs_fn、commit_fn 可以換成假的（測試用）。"""
    checks = []
    for spec in workflows or DEFAULT_WORKFLOWS:
        runs = runs_fn(spec["name"])
        if not runs:
            checks.append({"level": "warn", "name": spec.get("label") or spec["name"], "note": "查不到執行紀錄（gh 失敗或從未執行）"})
        else:
            checks.append(check_workflow(spec, runs, now))
    checks.append(check_commit_age(commit_fn(root), now))
    checks.append(check_market_stress(_load_json(root / "state" / "market_stress.json", {}).get("days", []), now))
    index = _load_json(root / "research" / "index.json", {})
    pending = {p.stem for p in (root / "research" / "pending").glob("*.json")} if (root / "research" / "pending").exists() else set()
    queue = []
    qdir = root / "state" / "research_queue"
    for f in sorted(qdir.glob("*.json")) if qdir.exists() else []:
        d = _load_json(f, None)
        if isinstance(d, dict):
            queue.append(d)
    checks.append(check_research_queue(queue, set(index) | pending, now))
    fut = _load_json(root / "state" / "futures_day.json", {})
    wd = prev_weekday(now)
    checks.append(check_session_ticks("期貨日盤報價", fut.get("today"), wd.strftime("%Y-%m-%d"), wd.replace(hour=13, minute=30)))
    checks.append(check_session_ticks("期貨夜盤報價", fut.get("night"), wd.strftime("%Y-%m-%d"), (wd + timedelta(days=1)).replace(hour=5, minute=0)))
    return checks
