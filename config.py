import os

# Google OAuth settings (loaded from Render environment variables)
GOOGLE_CLIENT_ID = os.getenv(
    "GOOGLE_CLIENT_ID",
    "1050767615707-gtouusnqadtpf9fafl76ih4qlmevuo5r.apps.googleusercontent.com"
)

GOOGLE_CLIENT_SECRET = os.getenv(
    "GOOGLE_CLIENT_SECRET",
    "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"
)

# Localhost for development, Render URL in production
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:4173/auth/google/callback"
)

# Secret key for signing sessions
APP_SECRET_KEY = os.getenv(
    "APP_SECRET_KEY",
    "ROAD_MUSIC_9fX2@LmQ7#vT81zKpR4nY!aD6wBc3HsU"
)