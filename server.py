from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs
import base64
import hashlib
import hmac
import json
import secrets
import time
import urllib.error
import urllib.request
import os

from config import (
    APP_SECRET_KEY,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
)


ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("PORT", 4173))
SONGS_FILE = ROOT / "songs.json"
AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
TOKENINFO_ENDPOINT = "https://oauth2.googleapis.com/tokeninfo"
SESSION_COOKIE = "road_music_session"
STATE_COOKIE = "road_music_state"


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


def load_songs():
    if not SONGS_FILE.exists():
        return []

    with SONGS_FILE.open("r", encoding="utf-8") as file:
        songs = json.load(file)

    cleaned = []
    for song in songs:
        if not song.get("id") or not song.get("title") or not song.get("audioUrl"):
            continue
        cleaned.append(
            {
                "id": str(song.get("id")),
                "title": song.get("title", "Unknown song"),
                "artist": song.get("artist", "Unknown artist"),
                "album": song.get("album", ""),
                "artwork": song.get("artwork", ""),
                "audioUrl": song.get("audioUrl", ""),
            }
        )
    return cleaned


def search_songs(query):
    songs = load_songs()
    words = normalize(query).split()
    if not words:
        return songs[:48]

    matches = []
    for song in songs:
        haystack = normalize(f"{song['title']} {song['artist']} {song['album']}")
        if all(word in haystack for word in words):
            matches.append(song)
    return matches[:48]


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
            self.send_json({"songs": search_songs(query)})
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
