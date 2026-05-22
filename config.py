# Local development Google OAuth settings.
# Do not publish real secrets to GitHub or a public repo.

GOOGLE_CLIENT_ID = "1050767615707-gtouusnqadtpf9fafl76ih4qlmevuo5r.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"

# Must match the redirect URI configured in Google Cloud Console.
GOOGLE_REDIRECT_URI = "http://localhost:4173/auth/google/callback"

# Change this to any long random string before sharing the app.
APP_SECRET_KEY = "change-this-road-music-secret-key"
