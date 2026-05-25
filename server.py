from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs
import base64
import concurrent.futures
import hashlib
import hmac
import json
import secrets
import re
import threading
import time
import urllib.error
import urllib.request
import os

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

from config import (
    APP_SECRET_KEY,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
)


ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("PORT", 4173))
YTDLP_CACHE_DIR = str(ROOT / ".yt-dlp-cache")
AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
TOKENINFO_ENDPOINT = "https://oauth2.googleapis.com/tokeninfo"
SESSION_COOKIE = "road_music_session"
STATE_COOKIE = "road_music_state"
CACHE_SECONDS = 600
RESOLVE_CACHE_SECONDS = 600
PREFETCH_LIMIT = 8
MAX_RESULTS = 48
BAD_RESULT_WORDS = (
    "nightcore",
    "slowed",
    "reverb",
    "remix",
    "lofi",
    "sped up",
    "speed up",
    "bass boosted",
    "karaoke",
    "instrumental",
    "cover",
    "mashup",
    "8d",
)
PREFERRED_WORDS = ("official", "audio", "video", "lyrics", "topic", "vevo")
POPULAR_ARTISTS = (
    "arijit singh",
    "imagine dragons",
    "ed sheeran",
    "the weeknd",
    "dua lipa",
    "taylor swift",
    "justin bieber",
    "charlie puth",
    "sia",
    "alan walker",
)
SEARCH_HINTS = {
    "believer": "Believer Imagine Dragons",
    "perfect": "Perfect Ed Sheeran",
    "tum hi ho": "Tum Hi Ho Arijit Singh",
    "kesariya": "Kesariya Arijit Singh",
    "blinding lights": "Blinding Lights The Weeknd",
}
TRENDING_QUERIES = [
    "Believer Imagine Dragons official audio",
    "Perfect Ed Sheeran official audio",
    "Tum Hi Ho Arijit Singh official audio",
    "Kesariya Arijit Singh official audio",
    "Blinding Lights The Weeknd official audio",
    "Shape of You Ed Sheeran official audio",
    "Starboy The Weeknd official audio",
    "Heat Waves Glass Animals official audio",
    "Levitating Dua Lipa official audio",
    "Senorita Shawn Mendes Camila Cabello official audio",
    "Attention Charlie Puth official audio",
    "Cheap Thrills Sia official audio",
    "Counting Stars OneRepublic official audio",
    "Unstoppable Sia official audio",
    "Until I Found You Stephen Sanchez official audio",
    "Apna Bana Le Arijit Singh official audio",
    "Chaleya Arijit Singh Shilpa Rao official audio",
    "Raataan Lambiyan Jubin Nautiyal official audio",
    "Tujhe Kitna Chahne Lage Arijit Singh official audio",
    "Phir Aur Kya Chahiye Arijit Singh official audio",
    "Heeriye Arijit Singh Jasleen Royal official audio",
    "O Maahi Arijit Singh official audio",
    "Satranga Arijit Singh official audio",
    "Tere Pyaar Mein Arijit Singh official audio",
    "Ranjha B Praak Jasleen Royal official audio",
    "Shayad Arijit Singh official audio",
    "Ghungroo Arijit Singh Shilpa Rao official audio",
    "Tum Se Hi Mohit Chauhan official audio",
    "Tu Jaane Na Atif Aslam official audio",
    "Tera Ban Jaunga Akhil Sachdeva official audio",
    "Peaches Justin Bieber official audio",
    "Stay The Kid LAROI Justin Bieber official audio",
    "As It Was Harry Styles official audio",
    "Flowers Miley Cyrus official audio",
    "Cruel Summer Taylor Swift official audio",
    "Anti Hero Taylor Swift official audio",
    "Someone You Loved Lewis Capaldi official audio",
    "Memories Maroon 5 official audio",
    "Bad Habits Ed Sheeran official audio",
    "Dance Monkey Tones and I official audio",
    "Lovely Billie Eilish Khalid official audio",
    "Let Me Love You DJ Snake Justin Bieber official audio",
    "Faded Alan Walker official audio",
    "Alone Alan Walker official audio",
    "Agar Tum Saath Ho Arijit Singh Alka Yagnik official audio",
    "Kabira Arijit Singh Harshdeep Kaur official audio",
    "Ilahi Arijit Singh official audio",
    "Kun Faya Kun A R Rahman Javed Ali Mohit Chauhan official audio",
]
_cache = {}
_cache_lock = threading.Lock()
_resolve_cache = {}
_resolve_cache_lock = threading.Lock()
_prefetching = set()
_prefetch_lock = threading.Lock()
_resolver_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
_track_lookup = {}
_browser_cookies_available = None
_youtube_blocked_until = 0


class QuietYtdlpLogger:
    def debug(self, message):
        pass

    def warning(self, message):
        pass

    def error(self, message):
        pass


def b64url(data):
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def b64url_decode(data):
    padded = data + "=" * (-len(data) % 4)
    return json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")))


def sign(value):
    return hmac.new(APP_SECRET_KEY.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def make_session(user):
    payload = b64url({"user": user, "iat": int(time.time())})
    return f"{payload}.{sign(payload)}"


def read_session(cookie_header):
    if not cookie_header:
        return None

    cookies = SimpleCookie(cookie_header)
    morsel = cookies.get(SESSION_COOKIE)
    if not morsel or "." not in morsel.value:
        return None

    payload, signature = morsel.value.rsplit(".", 1)
    if not hmac.compare_digest(signature, sign(payload)):
        return None

    try:
      return b64url_decode(payload).get("user")
    except Exception:
      return None


def http_post_json(url, payload):
    body = urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def http_get_json(url, params):
    with urllib.request.urlopen(f"{url}?{urlencode(params)}", timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize(value):
    return " ".join(str(value or "").lower().split())


def cached(cache_key, factory):
    now = time.time()
    with _cache_lock:
        item = _cache.get(cache_key)
        if item and now - item["time"] < CACHE_SECONDS:
            return item["value"]

    value = factory()
    with _cache_lock:
        _cache[cache_key] = {"time": now, "value": value}
    return value


def resolver_cache_key(track_query):
    parts = [
        track_query.get("id", ""),
        track_query.get("sourceUrl", ""),
        track_query.get("query", ""),
        track_query.get("title", ""),
        track_query.get("artist", ""),
    ]
    return hashlib.sha1(normalize(" ".join(parts)).encode("utf-8")).hexdigest()


def get_cached_stream(cache_key, log=True):
    now = time.time()
    with _resolve_cache_lock:
        item = _resolve_cache.get(cache_key)
        if item and item.get("expires", 0) > now and is_direct_media_url(item.get("audioUrl")):
            if log:
                print(f"[resolver] cache hit source={item.get('source', 'unknown')}")
            return item.get("audioUrl")
        if item:
            _resolve_cache.pop(cache_key, None)
    if log:
        print("[resolver] cache miss")
    return ""


def set_cached_stream(cache_key, audio_url, source, metadata=None):
    if not is_direct_media_url(audio_url):
        return
    with _resolve_cache_lock:
        _resolve_cache[cache_key] = {
            "audioUrl": audio_url,
            "expires": time.time() + RESOLVE_CACHE_SECONDS,
            "source": source,
            "metadata": metadata or {},
        }


def prefetch_playable_streams(tracks):
    for track in tracks[:PREFETCH_LIMIT]:
        cache_key = resolver_cache_key(track)
        if get_cached_stream(cache_key, log=False):
            continue
        with _prefetch_lock:
            if cache_key in _prefetching:
                continue
            _prefetching.add(cache_key)
        _resolver_executor.submit(prefetch_one_track, dict(track), cache_key)


def hydrate_cached_audio_urls(tracks):
    hydrated = []
    for track in tracks:
        item = dict(track)
        cached_url = get_cached_stream(resolver_cache_key(item), log=False)
        if cached_url:
            item["audioUrl"] = cached_url
        hydrated.append(item)
    return hydrated


def prefetch_one_track(track, cache_key):
    try:
        print(f"[resolver] prefetch start {track.get('title', '')}")
        resolve_audio_stream(track, 0, use_cache=True)
    finally:
        with _prefetch_lock:
            _prefetching.discard(cache_key)


def normalize_track_name(value):
    text = re.sub(r"\([^)]*(official|video|audio|lyrics|lyric|hd|4k)[^)]*\)", "", str(value or ""), flags=re.I)
    text = re.sub(r"\[[^\]]*(official|video|audio|lyrics|lyric|hd|4k)[^\]]*\]", "", text, flags=re.I)
    text = re.sub(r"\b(official|music|video|audio|lyrics?|full song|hd|4k)\b", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text.replace("|", " ")).strip(" -")
    return text or "Unknown song"


def make_track_id(title, artist, source_id=""):
    raw = normalize(f"{title} {artist} {source_id}") or secrets.token_hex(8)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def split_title_artist(entry):
    raw_title = entry.get("title") or "Unknown song"
    artist = entry.get("artist") or entry.get("creator") or entry.get("uploader") or entry.get("channel") or "Unknown artist"
    title = raw_title
    if " - " in raw_title:
        left, right = raw_title.split(" - ", 1)
        if len(left) < 60 and len(right) < 100:
            artist = left.strip() or artist
            title = right.strip() or title
    return normalize_track_name(title), normalize_track_name(artist)


def thumbnail_for(entry):
    thumbnails = entry.get("thumbnails") or []
    if thumbnails:
        return (thumbnails[-1] or {}).get("url", "")
    return entry.get("thumbnail") or ""


def result_score(entry, query):
    title, artist = split_title_artist(entry)
    haystack = normalize(f"{entry.get('title')} {entry.get('uploader')} {entry.get('channel')} {entry.get('artist')}")
    query_text = normalize(query)
    score = 0
    if all(word in haystack for word in query_text.split()[:5]):
        score += 20
    if normalize(title) == query_text:
        score += 18
    if query_text and query_text in normalize(f"{title} {artist}"):
        score += 14
    artist_text = normalize(artist)
    for known_artist in POPULAR_ARTISTS:
        if known_artist in query_text:
            score += 35 if known_artist in artist_text else -10
    if "@" in title:
        score -= 12
    if len(title) > len(query) * 1.6:
        score -= 8
    score += sum(4 for word in PREFERRED_WORDS if word in haystack)
    score -= sum(30 for word in BAD_RESULT_WORDS if word in haystack)
    duration = entry.get("duration") or 0
    if duration and (duration < 75 or duration > 780):
        score -= 18
    if entry.get("uploader", "").endswith(" - Topic"):
        score += 10
    return score


def ydl_search(search_query, limit=12, source="ytsearch"):
    if yt_dlp is None:
        return []

    options = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "socket_timeout": 8,
        "noplaylist": True,
        "cachedir": YTDLP_CACHE_DIR,
        "logger": QuietYtdlpLogger(),
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(f"{source}{limit}:{search_query}", download=False)
        return (info or {}).get("entries") or []
    except Exception:
        return []


def clean_track_result(entry, query=""):
    if not entry:
        return None

    title, artist = split_title_artist(entry)
    if normalize(title) in {"unknown song", "deleted video", "private video"}:
        return None

    source_url = entry.get("webpage_url") or entry.get("url") or ""
    source_id = entry.get("id") or source_url
    track = {
        "id": make_track_id(title, artist, source_id),
        "title": title,
        "artist": artist,
        "album": entry.get("album") or "",
        "artwork": thumbnail_for(entry),
        "audioUrl": "",
        "sourceUrl": source_url,
        "query": normalize_track_name(query or f"{title} {artist}"),
    }
    _track_lookup[track["id"]] = track
    return track


def clean_seed_result(query):
    words = query.replace("official audio", "").replace("official video", "").strip()
    title = words
    artist = "Unknown artist"
    for marker in (" Imagine Dragons", " Ed Sheeran", " Arijit Singh", " The Weeknd", " Dua Lipa", " Charlie Puth"):
        if marker in words:
            title = words.replace(marker, "").strip()
            artist = marker.strip()
            break
    return {
        "id": make_track_id(title, artist, query),
        "title": title,
        "artist": artist,
        "album": "",
        "artwork": "",
        "audioUrl": "",
        "sourceUrl": "",
        "query": query,
    }


def search_dynamic_songs(query):
    term = normalize_track_name(query)
    search_term = SEARCH_HINTS.get(normalize(term), term)

    def factory():
        entries = ydl_search(f"{search_term} official audio", 18, "ytsearch")
        entries = sorted(entries, key=lambda item: result_score(item, search_term), reverse=True)
        tracks = []
        seen = set()
        for entry in entries:
            if result_score(entry, term) < -10:
                continue
            track = clean_track_result(entry, term)
            if not track or track["id"] in seen:
                continue
            seen.add(track["id"])
            tracks.append(track)
        return tracks[:MAX_RESULTS]

    return cached(("search", normalize(term)), factory)


def get_trending_songs():
    def factory():
        tracks = []
        seen = set()

        def fetch_one(seed):
            entries = ydl_search(seed, 3, "ytsearch")
            entries = sorted(entries, key=lambda item: result_score(item, seed), reverse=True)
            return clean_track_result(entries[0], seed) if entries else clean_seed_result(seed)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(fetch_one, seed) for seed in TRENDING_QUERIES]
            try:
                for future in concurrent.futures.as_completed(futures, timeout=22):
                    track = future.result()
                    if track and track["id"] not in seen:
                        seen.add(track["id"])
                        tracks.append(track)
                    if len(tracks) >= MAX_RESULTS:
                        break
            except concurrent.futures.TimeoutError:
                pass

        for seed in TRENDING_QUERIES:
            if len(tracks) >= MAX_RESULTS:
                break
            fallback = clean_seed_result(seed)
            if fallback["id"] not in seen:
                seen.add(fallback["id"])
                tracks.append(fallback)
        return tracks[:MAX_RESULTS]

    return cached(("trending", "global"), factory)


def stream_from_entry(entry):
    def is_playable_format(item):
        url = item.get("url") or ""
        protocol = str(item.get("protocol") or "").lower()
        acodec = item.get("acodec")
        return (
            url
            and is_direct_media_url(url)
            and "m3u8" not in protocol
            and "manifest" not in protocol
            and acodec
            and acodec != "none"
            and item.get("vcodec") == "none"
        )

    def format_score(item):
        url = item.get("url") or ""
        ext = str(item.get("ext") or "").lower()
        protocol = str(item.get("protocol") or "").lower()
        preferred_ext = ext in {"mp3", "m4a", "webm", "opus", "ogg"}
        plain_http = protocol in {"http", "https"} and is_direct_media_url(url)
        return (
            item.get("vcodec") == "none",
            plain_http,
            preferred_ext,
            item.get("abr") or 0,
            item.get("tbr") or 0,
        )

    formats = sorted(
        entry.get("formats") or [],
        key=format_score,
        reverse=True,
    )
    for fmt in formats:
        url = fmt.get("url")
        if is_playable_format(fmt):
            return url
    fallback = entry.get("url") or ""
    return fallback if is_direct_media_url(fallback) else ""


def is_direct_media_url(url):
    raw_url = str(url or "").lower()
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if "youtube.com" in host and path.startswith("/watch"):
        return False
    if "youtu.be" in host or "soundcloud.com" in host:
        return False
    if any(bad in raw_url for bad in (".m3u8", ".mpd", "sndcdn.com/playlist", "cf-hls-media.sndcdn.com", "manifest")):
        return False
    return True


def source_label(url):
    host = urlparse(str(url or "")).netloc.lower()
    if "youtube" in host or "youtu.be" in host:
        return "youtube"
    if "soundcloud" in host:
        return "soundcloud"
    return host or "unknown"


def youtube_is_blocked():
    return time.time() < _youtube_blocked_until


def note_youtube_error(error):
    global _youtube_blocked_until
    message = str(error).lower()
    if "sign in to confirm" in message or "not a bot" in message:
        _youtube_blocked_until = time.time() + 300
        print("[resolver] youtube bot guard active for 300s")


def is_local_dev():
    return not os.environ.get("RENDER") and os.environ.get("ROADMUSIC_USE_BROWSER_COOKIES", "1") != "0"


def ydl_resolve_option_variants(base_options):
    global _browser_cookies_available
    variants = []
    if is_local_dev() and _browser_cookies_available is not False:
        with_cookies = dict(base_options)
        with_cookies["cookiesfrombrowser"] = ("chrome",)
        variants.append(with_cookies)
    variants.append(base_options)
    return variants


def extract_stream_with_options(candidate, options):
    global _browser_cookies_available
    last_error = None
    for ydl_options in ydl_resolve_option_variants(options):
        using_cookies = "cookiesfrombrowser" in ydl_options
        try:
            with yt_dlp.YoutubeDL(ydl_options) as ydl:
                info = ydl.extract_info(candidate, download=False)
            if using_cookies:
                _browser_cookies_available = True
            return stream_from_entry(info or {})
        except Exception as error:
            last_error = error
            message = str(error).lower()
            if using_cookies and any(text in message for text in ("could not find", "browser", "cookie", "chrome")):
                _browser_cookies_available = False
            continue
    if last_error:
        raise last_error
    return ""


def resolve_audio_stream(track_query, attempt=0, use_cache=True):
    if yt_dlp is None:
        print("[resolve] yt-dlp is not installed")
        return ""

    started = time.time()
    cache_key = resolver_cache_key(track_query)
    if use_cache and int(attempt or 0) == 0:
        cached_url = get_cached_stream(cache_key)
        if cached_url:
            print(f"[resolver] resolve duration {time.time() - started:.2f}s")
            return cached_url

    candidates = []
    source_url = track_query.get("sourceUrl", "")
    query = track_query.get("query") or f"{track_query.get('title', '')} {track_query.get('artist', '')}".strip()
    if source_url:
        candidates.append(source_url)

    for search_term, source, limit in (
        (f"{query} official audio", "ytsearch", 2),
        (f"{query} official video", "ytsearch", 1),
        (query, "scsearch", 6),
    ):
        if source == "ytsearch" and youtube_is_blocked():
            continue
        entries = ydl_search(search_term, limit, source)
        entries = sorted(entries, key=lambda item: result_score(item, query), reverse=True)
        candidates.extend(entry.get("webpage_url") or entry.get("url") for entry in entries if entry)

    options = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "skip_download": True,
        "socket_timeout": 7,
        "retries": 0,
        "fragment_retries": 0,
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "noplaylist": True,
        "cachedir": YTDLP_CACHE_DIR,
        "logger": QuietYtdlpLogger(),
    }
    tried = []
    youtube_count = 0
    soundcloud_count = 0
    for candidate in candidates:
        if not candidate or candidate in tried:
            continue
        label = source_label(candidate)
        if label == "youtube":
            if youtube_is_blocked():
                continue
            youtube_count += 1
            if youtube_count > 3:
                continue
        if label == "soundcloud":
            soundcloud_count += 1
            if soundcloud_count > 5:
                continue
        tried.append(candidate)

    skipped = max(0, int(attempt or 0))
    for candidate in tried[skipped:]:
        label = source_label(candidate)
        if label == "youtube" and youtube_is_blocked():
            continue
        print(f"[resolve] trying {label} source: {candidate}")
        try:
            stream_url = extract_stream_with_options(candidate, options)
            if stream_url:
                set_cached_stream(cache_key, stream_url, label, {"candidate": candidate})
                if label == "youtube":
                    print("[resolver] youtube success")
                else:
                    print("[resolver] fallback used")
                print(f"[resolve] success direct stream from {label}")
                print(f"[resolver] resolve duration {time.time() - started:.2f}s")
                return stream_url
            print(f"[resolve] no direct browser-playable stream from {label}")
        except Exception as error:
            if label == "youtube":
                note_youtube_error(error)
            print(f"[resolve] failed {label} source: {error}")

    if skipped:
        print(f"[resolve] alternate sources failed for query: {query}")
        print(f"[resolver] resolve duration {time.time() - started:.2f}s")
        return ""

    for source, search_term in (
        ("ytsearch2", f"{query} official audio"),
        ("scsearch8", query),
    ):
        if source.startswith("ytsearch") and youtube_is_blocked():
            continue
        print(f"[resolve] trying direct search extraction: {source}:{search_term}")
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(f"{source}:{search_term}", download=False)
            entries = sorted((info or {}).get("entries") or [], key=lambda item: result_score(item, query), reverse=True)
            for entry in entries:
                stream_url = stream_from_entry(entry or {})
                if stream_url:
                    cache_source = "soundcloud-search" if source.startswith("scsearch") else "youtube-search"
                    set_cached_stream(cache_key, stream_url, cache_source, {"search": search_term})
                    print(f"[resolve] success direct stream from {cache_source} extraction")
                    print("[resolver] resolve duration {0:.2f}s".format(time.time() - started))
                    return stream_url
        except Exception as error:
            if source.startswith("ytsearch"):
                note_youtube_error(error)
            print(f"[resolve] direct search extraction failed: {error}")

    print(f"[resolve] all sources failed for query: {query}")
    print(f"[resolver] resolve duration {time.time() - started:.2f}s")
    return ""


class RoadMusicHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        parsed_path = urlparse(path).path
        if parsed_path == "/":
            parsed_path = "/index.html"
        return str(ROOT / parsed_path.lstrip("/"))

    def send_json(self, data, status=HTTPStatus.OK):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_redirect(self, location, cookies=None):
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        if cookies:
            for cookie in cookies:
                self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/me":
            user = read_session(self.headers.get("Cookie"))
            self.send_json({"user": user})
            return

        if parsed.path == "/api/auth-status":
            enabled = not GOOGLE_CLIENT_ID.startswith("PASTE_") and not GOOGLE_CLIENT_SECRET.startswith("PASTE_")
            self.send_json({"googleEnabled": enabled})
            return

        if parsed.path == "/api/songs":
            query = parse_qs(parsed.query).get("q", [""])[0]
            songs = search_dynamic_songs(query) if normalize(query) else get_trending_songs()
            songs = hydrate_cached_audio_urls(songs)
            prefetch_playable_streams(songs)
            self.send_json({"songs": songs})
            return

        if parsed.path == "/api/resolve":
            params = parse_qs(parsed.query)
            track_id = params.get("id", [""])[0]
            try:
                attempt = int(params.get("attempt", ["0"])[0] or 0)
            except ValueError:
                attempt = 0
            track = dict(_track_lookup.get(track_id, {}))
            track.update(
                {
                    "id": track_id,
                    "title": params.get("title", [track.get("title", "")])[0],
                    "artist": params.get("artist", [track.get("artist", "")])[0],
                    "sourceUrl": params.get("sourceUrl", [track.get("sourceUrl", "")])[0],
                    "query": params.get("query", [track.get("query", "")])[0],
                }
            )
            print(f"[resolve] request id={track_id} title={track.get('title', '')} attempt={attempt}")
            stream_url = resolve_audio_stream(track, attempt)
            if not stream_url or not is_direct_media_url(stream_url):
                print(f"[resolve] rejected non-playable final url: {stream_url}")
                self.send_json({"error": "This song could not be played right now."}, HTTPStatus.BAD_GATEWAY)
                return
            self.send_json({"audioUrl": stream_url})
            return

        if parsed.path == "/auth/google":
            self.start_google_login()
            return

        if parsed.path == "/auth/google/callback":
            self.finish_google_login(parsed)
            return

        if parsed.path == "/auth/logout":
            expired = f"{SESSION_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax"
            self.send_redirect("/", [expired])
            return

        super().do_GET()

    def start_google_login(self):
        if GOOGLE_CLIENT_ID.startswith("PASTE_") or GOOGLE_CLIENT_SECRET.startswith("PASTE_"):
            self.send_json(
                {"error": "Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in config.py first."},
                HTTPStatus.BAD_REQUEST,
            )
            return

        state = secrets.token_urlsafe(24)
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
        state_cookie = f"{STATE_COOKIE}={state}; Path=/; HttpOnly; SameSite=Lax; Max-Age=600"
        self.send_redirect(f"{AUTH_ENDPOINT}?{urlencode(params)}", [state_cookie])

    def finish_google_login(self, parsed):
        query = parse_qs(parsed.query)
        code = query.get("code", [""])[0]
        state = query.get("state", [""])[0]
        cookies = SimpleCookie(self.headers.get("Cookie"))
        saved_state = cookies.get(STATE_COOKIE).value if cookies.get(STATE_COOKIE) else ""

        if not code or not state or not hmac.compare_digest(state, saved_state):
            self.send_json({"error": "Google login state check failed."}, HTTPStatus.BAD_REQUEST)
            return

        try:
            token_data = http_post_json(
                TOKEN_ENDPOINT,
                {
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            profile = http_get_json(TOKENINFO_ENDPOINT, {"id_token": token_data["id_token"]})

            if profile.get("aud") != GOOGLE_CLIENT_ID:
                self.send_json({"error": "Google token audience did not match this app."}, HTTPStatus.BAD_REQUEST)
                return

            user = {
                "name": profile.get("name") or profile.get("email") or "Google listener",
                "email": profile.get("email"),
                "picture": profile.get("picture", ""),
            }
            session_cookie = f"{SESSION_COOKIE}={make_session(user)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000"
            clear_state = f"{STATE_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax"
            self.send_redirect("/", [session_cookie, clear_state])
        except (urllib.error.URLError, KeyError, json.JSONDecodeError) as error:
            self.send_json({"error": f"Google login failed: {error}"}, HTTPStatus.BAD_GATEWAY)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), RoadMusicHandler)
    print(f"Road-Music running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()
