import os
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()


def get_spotify_auth():
    return SpotifyOAuth(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
        scope=(
            "user-read-playback-state "
            "user-modify-playback-state "
            "user-read-currently-playing"
        ),
        open_browser=True,
        cache_path=".spotify_cache"
    )