
import base64
import hashlib
import json
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import requests

import json

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

# spotify API credentials
CLIENT_ID = config["client_id"]
REDIRECT_URI = config["redirect_uri"]

SCOPES = (
    "user-read-playback-state "
    "user-read-currently-playing "
    "user-modify-playback-state"
)

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"
TOKEN_FILE = Path("spotify_token.json")

auth_result = {}


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        params = parse_qs(parsed.query)
        if "error" in params:
            auth_result["error"] = params["error"][0]
        if "code" in params:
            auth_result["code"] = params["code"][0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h2>Spotify login complete.</h2>"
            b"<p>You can close this window and go back to the terminal.</p></body></html>"
        )

    def log_message(self, format, *args):
        pass


def generate_pkce_pair():
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("utf-8")
    return verifier, challenge


def save_token(token_data):
    token_data["expires_at"] = time.time() + token_data.get("expires_in", 3600) - 30
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2))


def load_token():
    if TOKEN_FILE.exists():
        return json.loads(TOKEN_FILE.read_text())
    return None


def refresh_token(refresh_tok):
    data = {
        "client_id": CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": refresh_tok,
    }
    response = requests.post(TOKEN_URL, data=data, timeout=20)
    response.raise_for_status()
    new_token = response.json()

    old = load_token() or {}
    if "refresh_token" not in new_token:
        new_token["refresh_token"] = old.get("refresh_token", refresh_tok)

    save_token(new_token)
    return new_token


def get_valid_token():
    token = load_token()

    if token and token.get("expires_at", 0) > time.time():
        return token

    if token and token.get("refresh_token"):
        return refresh_token(token["refresh_token"])

    return login_with_pkce()


def login_with_pkce():
    verifier, challenge = generate_pkce_pair()

    server = HTTPServer(("127.0.0.1", 8888), CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "show_dialog": "true",
    }

    url = f"{AUTH_URL}?{urlencode(params)}"
    print("\nOpen this URL if the browser does not open automatically:\n")
    print(url)
    print("\nWaiting for Spotify login...\n")
    webbrowser.open(url)

    while "code" not in auth_result and "error" not in auth_result:
        time.sleep(0.5)

    server.shutdown()

    if "error" in auth_result:
        raise RuntimeError(f"Spotify login failed: {auth_result['error']}")

    data = {
        "client_id": CLIENT_ID,
        "grant_type": "authorization_code",
        "code": auth_result["code"],
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    }

    response = requests.post(TOKEN_URL, data=data, timeout=20)
    response.raise_for_status()
    token = response.json()
    save_token(token)
    return token


def api_request(method, path, params=None, json_body=None):
    token = get_valid_token()
    headers = {"Authorization": f"Bearer {token['access_token']}"}

    response = requests.request(
        method=method,
        url=f"{API_BASE}{path}",
        headers=headers,
        params=params,
        json=json_body,
        timeout=20,
    )

    if response.status_code == 401 and token.get("refresh_token"):
        token = refresh_token(token["refresh_token"])
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        response = requests.request(
            method=method,
            url=f"{API_BASE}{path}",
            headers=headers,
            params=params,
            json=json_body,
            timeout=20,
        )

    if response.status_code == 204:
        return None

    if not response.ok:
        print(f"\nError {response.status_code}: {response.text}\n")
        return None

    return response.json()


def list_devices():
    data = api_request("GET", "/me/player/devices")
    if not data or not data.get("devices"):
        print("No Spotify devices found.")
        return []

    devices = data["devices"]
    print("\nAvailable devices:")
    for d in devices:
        active = " (active)" if d.get("is_active") else ""
        print(f"- {d['name']} | id={d['id']} | type={d['type']}{active}")
    return devices


def current_track():
    data = api_request("GET", "/me/player/currently-playing")
    if not data or not data.get("item"):
        print("Nothing is currently playing.")
        return

    item = data["item"]
    artists = ", ".join(a["name"] for a in item.get("artists", []))
    print(f"\nNow playing: {item['name']} — {artists}")
    print(f"Album: {item['album']['name']}")
    print(f"Progress: {data.get('progress_ms', 0) // 1000}s")


def transfer_playback(device_id):
    api_request("PUT", "/me/player", json_body={
        "device_ids": [device_id],
        "play": True
    })
    print("Playback transferred.")


def play(device_id=None):
    params = {"device_id": device_id} if device_id else None
    api_request("PUT", "/me/player/play", params=params, json_body={})
    print("Play command sent.")


def pause():
    api_request("PUT", "/me/player/pause")
    print("Pause command sent.")


def next_track():
    api_request("POST", "/me/player/next")
    print("Next-track command sent.")


def main():
    print("Spotify Raspberry Pi Controller")
    print("-" * 32)

    try:
        get_valid_token()
        print("Login successful.\n")
    except Exception as e:
        print(f"Login failed: {e}")
        return

    while True:
        print("""
1 - List devices
2 - Show current track
3 - Transfer playback to a device
4 - Play / resume
5 - Pause
6 - Next track
q - Quit
""")
        choice = input("Choose: ").strip().lower()

        if choice == "1":
            list_devices()
        elif choice == "2":
            current_track()
        elif choice == "3":
            devices = list_devices()
            if devices:
                dev_id = input("Paste the target device id: ").strip()
                if dev_id:
                    transfer_playback(dev_id)
        elif choice == "4":
            dev_id = input("Optional device id (press Enter to skip): ").strip()
            play(dev_id or None)
        elif choice == "5":
            pause()
        elif choice == "6":
            next_track()
        elif choice == "q":
            break
        else:
            print("Invalid option.")


if __name__ == "__main__":
    main()



