#!/usr/bin/env python3
"""Build categorized IPTV M3U playlists from configured public sources."""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
PROMO_NAME = "Potplayer,Tivimate,OTT navigator可用，其它软件自行测试"
PROMO_URL = "https://raw.githubusercontent.com/mavin521/syiptv/main/123/1.m3u8"
SOURCES = [
    "https://raw.githubusercontent.com/cs3306/IPTV-Sources/main/data/output/iptv_collection.m3u",
    "https://live.zbds.top/tv/iptv4.m3u",
    "https://iptv-org.github.io/iptv/countries/hk.m3u",
    "https://iptv-org.github.io/iptv/countries/tw.m3u",
    "https://iptv-org.github.io/iptv/categories/sports.m3u",
]
HEADERS = {"User-Agent": "syiptv-playlist-updater/1.0"}
SESSION_TIMEOUT = (8, 18)
MAX_PER_PLAYLIST = 500
PROMO = ("#EXTINF:-1," + PROMO_NAME, PROMO_URL)


def fetch_source(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=SESSION_TIMEOUT)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text.lstrip("\ufeff")


def parse_m3u(text: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            current = line
        elif not line.startswith("#") and line.startswith(("http://", "https://")):
            if current:
                entries.append((current, line))
            current = None
    return entries


def label(info: str) -> str:
    if "," in info:
        return info.rsplit(",", 1)[-1].strip().lower()
    match = re.search(r'tvg-name="([^"]+)"', info, re.I)
    return (match.group(1) if match else info).lower()


def category(info: str, url: str) -> str | None:
    text = (info + " " + url).lower()
    mainland = [
        "cctv", "cgtn", "央视", "中央电视台", "卫视", "湖南", "浙江", "江苏",
        "东方卫视", "北京卫视", "广东卫视", "山东卫视", "河南卫视", "安徽卫视",
        "四川卫视", "深圳卫视", "凤凰中文", "凤凰资讯", "咪咕", "migu",
    ]
    hk_tw = [
        "tvb", "viutv", "rthk", "now新闻", "now news", "凤凰卫视", "凤凰中文",
        "凤凰资讯", "香港", "澳门", "澳視", "澳视", "港台", "中天", "民视", "民視",
        "东森", "東森", "三立", "tvbs", "华视", "華視", "台视", "台視", "公视",
        "公視", "年代", "八大", "壹电视", "壹電視", "台湾", "台灣",
    ]
    sports = [
        "sport", "体育", "體育", "足球", "篮球", "籃球", "nba", "ufc", "f1",
        "formula 1", "premier league", "la liga", "serie a", "bundesliga",
        "ligue 1", "champions league", "europa league", "espn", "fox sports",
        "dazn", "sky sports", "tnt sports", "beinsports", "咪咕体育", "咪咕體育",
    ]
    if any(x in text for x in ["咪咕体育", "咪咕體育", "migu sports", "migu体育", "migu體育"]):
        return "migu"
    if any(x in text for x in sports):
        return "sports"
    if any(x in text for x in hk_tw):
        return "gat"
    if any(x in text for x in mainland):
        return "live"
    return None


def reachable(url: str) -> bool:
    """Lightweight URL check; this does not guarantee the stream decodes or plays."""
    try:
        with requests.get(url, headers=HEADERS, timeout=(5, 8), stream=True, allow_redirects=True) as r:
            return 200 <= r.status_code < 400
    except requests.RequestException:
        try:
            r = requests.head(url, headers=HEADERS, timeout=(5, 6), allow_redirects=True)
            return 200 <= r.status_code < 400
        except requests.RequestException:
            return False


def dedupe(entries: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    result = []
    for info, url in entries:
        key = re.sub(r"\s+", " ", label(info)).strip() + "|" + url.strip().rstrip("/")
        if url == PROMO_URL or key in seen:
            continue
        seen.add(key)
        result.append((info, url))
    return result


def write_playlist(filename: str, entries: list[tuple[str, str]], stamp: str) -> None:
    lines = [
        "#EXTM3U",
        f"# Updated automatically: {stamp}",
        PROMO[0],
        PROMO[1],
    ]
    for info, url in entries[:MAX_PER_PLAYLIST]:
        lines.extend((info, url))
    (ROOT / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    collected: list[tuple[str, str]] = []
    failures = []
    for source in SOURCES:
        try:
            entries = parse_m3u(fetch_source(source))
            print(f"Fetched {len(entries)} entries: {source}")
            collected.extend(entries)
        except Exception as exc:
            failures.append(f"{source}: {exc}")
            print(f"WARNING: source failed: {source}: {exc}", file=sys.stderr)

    if not collected:
        print("ERROR: every source failed or contained no parsable entries; keeping existing playlists.", file=sys.stderr)
        return 1

    buckets: dict[str, list[tuple[str, str]]] = {"live": [], "gat": [], "migu": [], "sports": []}
    for info, url in dedupe(collected):
        target = category(info, url)
        if target:
            buckets[target].append((info, url))

    # Check each candidate URL once, concurrently. A successful HTTP response is not proof of playback.
    all_urls = list(dict.fromkeys(url for items in buckets.values() for _, url in items))
    status: dict[str, bool] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        futures = {pool.submit(reachable, url): url for url in all_urls}
        for future in concurrent.futures.as_completed(futures):
            status[futures[future]] = future.result()

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    files = {"live": "live.m3u", "gat": "gat.m3u", "migu": "migu.m3u", "sports": "sports.m3u"}
    for key, filename in files.items():
        good = [(info, url) for info, url in buckets[key] if status.get(url, False)]
        write_playlist(filename, good, stamp)
        print(f"Wrote {filename}: {len(good)} checked entries (+ promo link)")

    if failures:
        print(f"WARNING: {len(failures)} source(s) failed; outputs were built from the remaining sources.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
