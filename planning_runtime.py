import hashlib
import html
import json
import os
import random
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional


DEFAULT_LOCATION = "Tokyo, Japan"
DEFAULT_TIMEZONE = "Asia/Tokyo"

REFERENCE_SOURCES = [
    {
        "id": "JP-HOLIDAY-2026-CAO",
        "title": "Cabinet Office: National holidays in 2026",
        "url": "https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html",
        "confidence": 0.98,
        "summary": "Official Japanese Cabinet Office holiday table for 2026.",
    },
    {
        "id": "JP-SCHOOL-CLUB-JNTO",
        "title": "JAPAN Educational Travel: club activities in Japanese schools",
        "url": "https://education.jnto.go.jp/en/school-in-japan/school-life-in-japan/club-activities-in-japanese-schools/",
        "confidence": 0.82,
        "summary": "Explains bukatsudo as voluntary clubs, often after school and sometimes on holidays.",
    },
    {
        "id": "JP-HS-SCHEDULE-CAJ",
        "title": "Christian Academy in Japan: high school daily schedule",
        "url": "https://caj.ac.jp/info/index.php/High_School_Daily_Schedule",
        "confidence": 0.68,
        "summary": "Representative Japan-based high-school timetable with morning blocks, lunch, afternoon blocks, and club slots.",
    },
]

JAPAN_HOLIDAYS_2026 = {
    "2026-01-01": "元日",
    "2026-01-12": "成人の日",
    "2026-02-11": "建国記念の日",
    "2026-02-23": "天皇誕生日",
    "2026-03-20": "春分の日",
    "2026-04-29": "昭和の日",
    "2026-05-03": "憲法記念日",
    "2026-05-04": "みどりの日",
    "2026-05-05": "こどもの日",
    "2026-05-06": "休日",
    "2026-07-20": "海の日",
    "2026-08-11": "山の日",
    "2026-09-21": "敬老の日",
    "2026-09-22": "休日",
    "2026-09-23": "秋分の日",
    "2026-10-12": "スポーツの日",
    "2026-11-03": "文化の日",
    "2026-11-23": "勤労感謝の日",
}

BASE_WEEKDAY_BLOCKS = [
    ("07:00", "07:40", "wake_up", "起床、身支度、軽い朝食"),
    ("08:20", "12:30", "classes", "初星学園の授業"),
    ("12:30", "13:15", "lunch", "昼食と短い休憩"),
    ("13:20", "15:30", "classes", "午後の授業"),
    ("15:45", "17:20", "idol_training", "ボーカル/ダンス/表現レッスン"),
    ("17:30", "18:20", "student_life", "委員会、移動、軽い自主練"),
    ("19:30", "20:20", "homework", "課題と復習"),
    ("21:00", "21:35", "relationship_time", "プロデューサーへの連絡、日記、明日の準備"),
    ("22:30", "23:20", "rest", "入浴、花の手入れ、就寝準備"),
]

BASE_WEEKEND_BLOCKS = [
    ("08:30", "09:20", "wake_up", "遅めの起床、朝食"),
    ("10:00", "11:40", "self_training", "自主練、体幹、発声"),
    ("12:00", "13:00", "lunch", "昼食"),
    ("13:30", "15:00", "walk", "散歩、買い物、花を見る時間"),
    ("15:20", "16:40", "idol_training", "振り返り、歌詞確認、軽い練習"),
    ("18:30", "19:30", "cooking", "料理、作り置き"),
    ("21:00", "21:45", "relationship_time", "プロデューサーへの連絡、夢のような雑談"),
    ("22:30", "23:30", "rest", "早めに休むつもりで、少しだけ夜更かし"),
]

PERTURBATIONS = [
    ("unexpected_lesson", "急な表現レッスン追加", "quiet_pressure"),
    ("body_clock_check", "体内時計の確認を兼ねた早朝自主練", "discipline"),
    ("flower_errand", "生け花用の花を選ぶ寄り道", "soft_care"),
    ("producer_message", "プロデューサーへ少し長めの連絡", "relationship"),
    ("temari_thought", "まりちゃんのことを少し考えてしまう時間", "relationship_tension"),
    ("nap_overrun", "昼寝が少し長引く", "sleepiness"),
    ("cooking_practice", "料理の試作", "care"),
]


def _now() -> datetime:
    return datetime.now().astimezone()


def device_context(location: Optional[str] = None) -> Dict:
    now = _now()
    offset = now.strftime("%z")
    return {
        "timestamp": int(now.timestamp()),
        "iso": now.isoformat(timespec="seconds"),
        "date": now.date().isoformat(),
        "weekday": now.strftime("%A"),
        "utc_offset": f"{offset[:3]}:{offset[3:]}" if offset else "",
        "timezone": os.getenv("TZ") or time.tzname[0] or DEFAULT_TIMEZONE,
        "location": location or os.getenv("ROLEWEAVER_LOCAL_LOCATION") or DEFAULT_LOCATION,
    }


def week_start_for(target: Optional[date] = None) -> date:
    target = target or _now().date()
    return target - timedelta(days=target.weekday())


def planning_dir(memory_scope_path: Path) -> Path:
    path = memory_scope_path / "planning"
    path.mkdir(parents=True, exist_ok=True)
    return path


def schedule_path(memory_scope_path: Path) -> Path:
    return planning_dir(memory_scope_path) / "weekly_schedule.json"


def _seed_for(memory_scope_path: Path, week_start: date, role_name: str) -> int:
    raw = f"{memory_scope_path.resolve()}|{week_start.isoformat()}|{role_name}".encode("utf-8", errors="ignore")
    return int(hashlib.sha256(raw).hexdigest()[:16], 16)


def _time_to_minutes(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def _is_between(now: datetime, start: str, end: str) -> bool:
    minute = now.hour * 60 + now.minute
    return _time_to_minutes(start) <= minute < _time_to_minutes(end)


def _holiday_name(day: date) -> Optional[str]:
    return JAPAN_HOLIDAYS_2026.get(day.isoformat())


def _blocks_for_day(day: date, rng: random.Random) -> List[Dict]:
    holiday = _holiday_name(day)
    is_weekend = day.weekday() >= 5
    blocks = BASE_WEEKEND_BLOCKS if is_weekend or holiday else BASE_WEEKDAY_BLOCKS
    result = [
        {"start": start, "end": end, "kind": kind, "title": title}
        for start, end, kind, title in blocks
    ]
    if holiday:
        result.insert(1, {
            "start": "09:30",
            "end": "10:15",
            "kind": "holiday",
            "title": f"{holiday}。授業は薄く、休息と自主練を優先",
        })
    if rng.random() < 0.65:
        key, title, tag = rng.choice(PERTURBATIONS)
        hour = rng.choice(["06:40", "16:50", "20:30"])
        end_hour = {
            "06:40": "07:05",
            "16:50": "17:15",
            "20:30": "20:55",
        }[hour]
        result.append({"start": hour, "end": end_hour, "kind": key, "title": title, "tag": tag})
    result.sort(key=lambda item: item["start"])
    return result


def generate_weekly_schedule(
    memory_scope_path: Path,
    *,
    role_name: str = "RoleWeaver",
    location: Optional[str] = None,
    target_date: Optional[date] = None,
) -> Dict:
    start = week_start_for(target_date)
    rng = random.Random(_seed_for(memory_scope_path, start, role_name))
    context = device_context(location)
    days = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        days.append({
            "date": day.isoformat(),
            "weekday": day.strftime("%A"),
            "holiday": _holiday_name(day),
            "blocks": _blocks_for_day(day, rng),
        })
    schedule = {
        "schema_version": "1.0",
        "generated_at": _now().isoformat(timespec="seconds"),
        "week_start": start.isoformat(),
        "role_name": role_name,
        "location": context["location"],
        "timezone": context["timezone"],
        "device_context": context,
        "design_basis": {
            "model": "memory_reflection_planning",
            "sources": REFERENCE_SOURCES,
            "notes": [
                "This is a fictionalized role schedule, not an official Gakuen iDOLM@STER calendar.",
                "Japanese public holidays are integrated from Cabinet Office 2026 data.",
                "School and club blocks are representative references; role-specific idol lessons are generated as plausible planning state.",
            ],
        },
        "days": days,
    }
    save_schedule(memory_scope_path, schedule)
    return schedule


def load_schedule(memory_scope_path: Path) -> Optional[Dict]:
    path = schedule_path(memory_scope_path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def save_schedule(memory_scope_path: Path, schedule: Dict) -> None:
    schedule_path(memory_scope_path).write_text(
        json.dumps(schedule, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def ensure_weekly_schedule(
    memory_scope_path: Path,
    *,
    role_name: str = "RoleWeaver",
    location: Optional[str] = None,
    force: bool = False,
) -> Dict:
    current_week = week_start_for().isoformat()
    if not force:
        existing = load_schedule(memory_scope_path)
        if existing and existing.get("week_start") == current_week:
            return existing
    return generate_weekly_schedule(memory_scope_path, role_name=role_name, location=location)


def current_schedule_state(schedule: Dict, now: Optional[datetime] = None) -> Dict:
    now = now or _now()
    today = now.date().isoformat()
    today_plan = next((day for day in schedule.get("days", []) if day.get("date") == today), None)
    block = None
    if today_plan:
        for candidate in today_plan.get("blocks", []):
            if _is_between(now, candidate.get("start", "00:00"), candidate.get("end", "00:00")):
                block = candidate
                break
    return {
        "now": device_context(schedule.get("location")),
        "today": today_plan,
        "current_block": block,
    }


def render_planning_context(schedule: Dict, max_blocks: int = 8) -> str:
    state = current_schedule_state(schedule)
    now = state["now"]
    today = state.get("today") or {}
    block = state.get("current_block")
    lines = [
        "【現在時刻と生活状態】",
        f"- 現在: {now.get('iso')} / {now.get('timezone')} / {now.get('location')}",
        f"- 今週の予定生成日: {schedule.get('generated_at')} / week_start={schedule.get('week_start')}",
    ]
    if today:
        holiday = today.get("holiday")
        lines.append(f"- 今日: {today.get('date')} {today.get('weekday')}" + (f" / {holiday}" if holiday else ""))
        for item in (today.get("blocks") or [])[:max_blocks]:
            lines.append(f"  - {item.get('start')}-{item.get('end')} {item.get('title')}")
    if block:
        lines.append(f"- 今この役割は「{block.get('title')}」の時間帯にいる想定。")
    else:
        lines.append("- 今は明確な予定ブロック外。余白、移動、休息として扱う。")
    lines.append("この予定は人格を上書きしない。日常の現在地・気分・余白を作るための planning context としてのみ使う。")
    return "\n".join(lines)


def _fetch_search_page(url: str, timeout: int) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36 RoleWeaver/1.0"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6,ja;q=0.4",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "")
        charset_match = re.search(r"charset=([\w.-]+)", content_type, re.I)
        charset = charset_match.group(1) if charset_match else "utf-8"
        return response.read().decode(charset, errors="replace")


def _strip_html(value: str) -> str:
    return html.unescape(re.sub(r"<.*?>", "", value or "")).strip()


def _dedupe_results(results: List[Dict], limit: int) -> List[Dict]:
    deduped = []
    seen = set()
    for item in results:
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        if not title or not url:
            continue
        key = url.split("#", 1)[0]
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"title": title, "url": url})
        if len(deduped) >= limit:
            break
    return deduped


def _search_duckduckgo(query: str, limit: int, timeout: int) -> Dict:
    url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    text = _fetch_search_page(url, timeout)
    results = []
    pattern = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
    for match in pattern.finditer(text):
        href = html.unescape(match.group(1))
        title = _strip_html(match.group(2))
        if href.startswith("//duckduckgo.com/l/?"):
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            href = parsed.get("uddg", [href])[0]
        results.append({"title": title, "url": href})
    return {"query": query, "provider": "duckduckgo", "results": _dedupe_results(results, limit), "error": ""}


def _search_bing_cn(query: str, limit: int, timeout: int) -> Dict:
    params = urllib.parse.urlencode({"q": query, "cc": "CN", "setlang": "zh-Hans"})
    url = f"https://cn.bing.com/search?{params}"
    text = _fetch_search_page(url, timeout)
    results = []
    pattern = re.compile(r'<li[^>]+class="b_algo"[^>]*>.*?<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
    for match in pattern.finditer(text):
        results.append({"title": _strip_html(match.group(2)), "url": html.unescape(match.group(1))})
    return {"query": query, "provider": "bing_cn", "results": _dedupe_results(results, limit), "error": ""}


def _search_baidu(query: str, limit: int, timeout: int) -> Dict:
    params = urllib.parse.urlencode({"wd": query, "rn": str(max(limit, 10))})
    url = f"https://www.baidu.com/s?{params}"
    text = _fetch_search_page(url, timeout)
    results = []
    pattern = re.compile(r'<h3[^>]*class="[^"]*t[^"]*"[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
    for match in pattern.finditer(text):
        results.append({"title": _strip_html(match.group(2)), "url": html.unescape(match.group(1))})
    if not results:
        fallback = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
        for match in fallback.finditer(text):
            href = html.unescape(match.group(1))
            title = _strip_html(match.group(2))
            if href.startswith("http") and title:
                results.append({"title": title, "url": href})
    return {"query": query, "provider": "baidu", "results": _dedupe_results(results, limit), "error": ""}


def web_search(query: str, limit: int = 5, timeout: int = 8, provider: Optional[str] = None) -> Dict:
    query = (query or "").strip()
    if not query:
        return {"query": query, "results": [], "error": "query is empty"}
    requested = (provider or os.getenv("ROLEWEAVER_WEB_SEARCH_PROVIDER") or "auto").strip().lower()
    providers = {
        "bing_cn": _search_bing_cn,
        "bing": _search_bing_cn,
        "baidu": _search_baidu,
        "duckduckgo": _search_duckduckgo,
        "ddg": _search_duckduckgo,
    }
    if requested in {"auto", "china", "cn", "mainland"}:
        order = ["bing_cn", "baidu", "duckduckgo"]
    else:
        order = [requested]

    errors = []
    for name in order:
        searcher = providers.get(name)
        if not searcher:
            errors.append(f"{name}: unknown provider")
            continue
        try:
            result = searcher(query, limit, timeout)
        except Exception as exc:
            errors.append(f"{name}: {exc}")
            continue
        if result.get("results"):
            result["attempted_providers"] = order
            return result
        errors.append(f"{name}: no usable results")
    return {"query": query, "provider": requested, "attempted_providers": order, "results": [], "error": "; ".join(errors)}
