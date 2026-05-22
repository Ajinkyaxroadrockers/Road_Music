# Road-Music

A Spotify-style music web app themed after the provided Road-Music image.

## Run

Start the Python backend from this folder:

```powershell
python server.py
```

Then open:

```text
http://localhost:4173
```

## Features

- Search songs by title, artist, album, or partial text.
- Search is case-insensitive and trims extra spaces, so ` tere ` can match songs containing `tere`.
- Play, pause, previous, next, progress seeking, and auto-next.
- Create as many named playlists as you want.
- Save songs into the selected playlist.
- Add songs to a queue.
- Playlist and queue are stored per logged-in user in browser `localStorage`.
- Demo Google-style login works immediately for local testing.
- Real Google OAuth login runs through the Python backend.
- Full-length playback streams from cloud/catalog URLs listed in `songs.json`.

## Google Login Setup

To use real Google login:

1. Create an OAuth client in Google Cloud Console for a web app.
2. Add your local origin, for example `http://localhost:4173`.
3. Add this redirect URI: `http://localhost:4173/auth/google/callback`.
4. Paste your keys into `config.py`:

```python
GOOGLE_CLIENT_ID = "your-client-id.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "your-client-secret"
```

5. Run `python server.py`.

## Music Catalog

Full songs are read from `songs.json`. Each song should point to a public or signed cloud-storage audio URL:

```json
{
  "id": "unique-song-id",
  "title": "Song Name",
  "artist": "Artist Name",
  "album": "Album Name",
  "artwork": "https://your-cloud.com/cover.jpg",
  "audioUrl": "https://your-cloud.com/song.mp3"
}
```

You can use AWS S3, Cloudflare R2, Google Cloud Storage, Firebase Storage, Supabase Storage, or any CDN. The audio URL must be playable by the browser and allow cross-origin streaming.

This app cannot legally include or stream Spotify's full catalog directly without Spotify approval, OAuth setup, and playback licensing. Only upload songs you own, made yourself, or have rights to distribute.
