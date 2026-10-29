"""Custom Media Resolvers for specialized and obfuscated streaming domains."""

import re
import html
import urllib.parse
from typing import Optional, Dict, Any
import requests


def resolve_jwplyr(url: str) -> Dict[str, Any]:
    """Resolve direct video stream from jwplyr.com / vidoy.com player architecture."""
    # Matches /e/<id>, /d/<id>, or /<id>
    m = re.search(r"(?:jwplyr\.com|vidoy\.com|vidoy\.asia)/(?:e/|d/)?([a-zA-Z0-9_-]+)", url)
    if not m:
        raise ValueError("Format URL jwplyr / vidoy tidak valid.")
    video_id = m.group(1)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    embed_url = f"https://jwplyr.com/e/{video_id}"
    try:
        resp1 = requests.get(embed_url, headers=headers, allow_redirects=False, timeout=12)
    except requests.RequestException as e:
        raise ValueError(f"Gagal menghubungi server jwplyr.com: {str(e)}")

    # Check if redirected to 404 (indicates deleted/expired video)
    if resp1.status_code in (301, 302, 303, 307, 308):
        loc = resp1.headers.get("Location", "")
        if "404" in loc:
            raise ValueError(f"Video ID '{video_id}' sudah kedaluwarsa atau dihapus dari host jwplyr.com (Server mengembalikan status 404).")
        # Follow legitimate redirect
        redirect_url = urllib.parse.urljoin(embed_url, loc)
        resp1 = requests.get(redirect_url, headers=headers, timeout=12)

    if resp1.status_code == 404:
        raise ValueError(f"Video ID '{video_id}' tidak ditemukan di jwplyr.com (404 Not Found).")

    html1 = resp1.text
    if "File is no longer available" in html1 or "File Not Found" in html1 or "file has expired" in html1.lower():
        raise ValueError(f"Video ID '{video_id}' sudah kedaluwarsa atau dihapus oleh penyedia konten.")

    # 1. Extract gateway token from embed
    src_match = re.search(r"var\s+SRC\s*=\s*['\"]([^'\"]+)['\"]", html1)
    if not src_match:
        # Check if direct video tag exists
        vid_match = re.search(r'<source\s+src=[\'"]([^\'"]+)', html1)
        if vid_match:
            return {
                "id": video_id,
                "title": f"jwplyr_{video_id}",
                "stream_url": vid_match.group(1),
                "thumbnail": "",
                "platform": "jwplyr",
                "headers": {"Referer": embed_url, "User-Agent": headers["User-Agent"]}
            }
        raise ValueError("Gagal menemukan token gateway stream pada player jwplyr.")

    src_path = src_match.group(1)
    gate_url = urllib.parse.urljoin("https://jwplyr.com", src_path)

    req_headers = dict(headers)
    req_headers["Referer"] = embed_url

    try:
        resp2 = requests.get(gate_url, headers=req_headers, timeout=12)
    except requests.RequestException as e:
        raise ValueError(f"Gagal mengakses gateway token jwplyr: {str(e)}")

    html2 = resp2.text

    # 2. Extract playerPath from gate
    path_match = re.search(r"const\s+playerPath\s*=\s*['\"]([^'\"]+)['\"]", html2)
    if not path_match:
        path_match = re.search(r'<link\s+rel=[\'"]prefetch[\'"]\s+href=[\'"]([^\'"]+)', html2)

    if not path_match:
        raise ValueError("Gagal mengekstrak playerPath stream dari gateway jwplyr.")

    raw_player_path = path_match.group(1)
    # Decode unicode escape sequences (e.g. \u0026 -> &)
    player_path = html.unescape(raw_player_path.encode("utf-8").decode("unicode_escape"))
    player_url = urllib.parse.urljoin("https://jwplyr.com", player_path)

    try:
        resp3 = requests.get(player_url, headers=req_headers, timeout=12)
    except requests.RequestException as e:
        raise ValueError(f"Gagal memuat stream player jwplyr: {str(e)}")

    html3 = resp3.text

    # 3. Extract title, direct video stream source, and poster
    title_m = re.search(r"<title>(.*?)</title>", html3)
    title = title_m.group(1).strip() if title_m else f"jwplyr_{video_id}"

    source_m = re.search(r'<source\s+src=[\'"]([^\'"]+)', html3)
    if not source_m:
        source_m = re.search(r'<video[^>]+src=[\'"]([^\'"]+)', html3)

    if not source_m:
        raise ValueError("Gagal mengekstrak direct source video (.mp4/.m3u8) dari player jwplyr.")

    stream_url = source_m.group(1)

    poster_m = re.search(r'poster=[\'"]([^\'"]+)', html3)
    poster = poster_m.group(1) if poster_m else ""

    return {
        "id": video_id,
        "title": title,
        "stream_url": stream_url,
        "thumbnail": poster,
        "platform": "jwplyr",
        "headers": {"Referer": "https://jwplyr.com/", "User-Agent": headers["User-Agent"]}
    }


def resolve_generic_html5(url: str) -> Optional[Dict[str, Any]]:
    """Inspect arbitrary webpage for direct HTML5 video elements or stream manifests."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return None
        text = r.text

        # Search for m3u8 or mp4 URLs
        stream_m = re.search(r'https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*', text)
        if stream_m:
            stream_url = stream_m.group(0)
            title_m = re.search(r"<title>(.*?)</title>", text)
            title = title_m.group(1).strip() if title_m else "Web Video Stream"
            return {
                "id": "generic_stream",
                "title": title,
                "stream_url": stream_url,
                "thumbnail": None,
                "platform": "Generic Stream",
                "headers": {"Referer": url, "User-Agent": headers["User-Agent"]}
            }
    except Exception:
        pass
    return None


def resolve_custom_stream(url: str) -> Optional[Dict[str, Any]]:
    """Route URL to domain-specific resolver if applicable."""
    lower_url = url.lower()
    if any(domain in lower_url for domain in ("jwplyr.com", "vidoy.com", "vidoy.asia")):
        return resolve_jwplyr(url)

    return None
