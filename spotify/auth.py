# spotify/auth.py
# Handles Spotify OAuth login using environment variables from .env.

import os
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()


def get_spotify_auth():
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI")

    if not client_id or not client_secret or not redirect_uri:
        raise ValueError(
            "Missing Spotify environment variables. "
            "Check SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, "
            "and SPOTIPY_REDIRECT_URI in your .env file."
        )

    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=(
            "user-read-playback-state "
            "user-modify-playback-state "
            "user-read-currently-playing"
        ),
        open_browser=True,
        cache_path=".spotify_cache"
    )
