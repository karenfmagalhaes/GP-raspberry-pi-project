# spotify/controller.py
# Controls Spotify playback using Spotipy.

import spotipy
from spotify.auth import get_spotify_auth


class SpotifyController:
    def __init__(self):
        self.sp = spotipy.Spotify(auth_manager=get_spotify_auth())
        self._device = None  # cached device object; cleared on API error

    # ------------------------------------------------------------------
    # Device resolution
    # ------------------------------------------------------------------

    def get_devices(self):
        try:
            return self.sp.devices().get("devices", [])
        except Exception as e:
            print(f"[Spotify] Device error: {e}")
            return []

    def get_active_device(self):
        devices = self.get_devices()
        for device in devices:
            if device.get("is_active"):
                return device
        return devices[0] if devices else None

    def get_active_device_id(self):
        device = self.get_active_device()
        return device.get("id") if device else None

    def _get_device(self):
        """Returns cached device, fetching from API only on first call or after an error."""
        if self._device is None:
            self._device = self.get_active_device()
        return self._device

    def _device_block_message(self, device):
        if not device:
            return "No active Spotify device"
        if device.get("is_restricted", False):
            return "This Spotify device is restricted"
        return None

    # ------------------------------------------------------------------
    # Playback controls
    # ------------------------------------------------------------------

    def play(self):
        device = self._get_device()
        block = self._device_block_message(device)
        if block:
            return block
        try:
            self.sp.start_playback(device_id=device["id"])
            return "Playing"
        except spotipy.SpotifyException:
            self._device = None
            return "Spotify error: device unavailable"
        except Exception as e:
            return f"Spotify error: {e}"

    def pause(self):
        device = self._get_device()
        block = self._device_block_message(device)
        if block:
            return block
        try:
            self.sp.pause_playback(device_id=device["id"])
            return "Paused"
        except spotipy.SpotifyException:
            self._device = None
            return "Spotify error: device unavailable"
        except Exception as e:
            return f"Spotify error: {e}"

    def next_track(self):
        device = self._get_device()
        block = self._device_block_message(device)
        if block:
            return block
        try:
            self.sp.next_track(device_id=device["id"])
            return "Next track"
        except spotipy.SpotifyException as e:
            self._device = None
            if "Restriction violated" in str(e):
                return "Next not allowed on this device/context"
            return f"Spotify error: {e}"
        except Exception as e:
            return f"Spotify error: {e}"

    def previous_track(self):
        device = self._get_device()
        block = self._device_block_message(device)
        if block:
            return block
        try:
            self.sp.previous_track(device_id=device["id"])
            return "Previous track"
        except spotipy.SpotifyException as e:
            self._device = None
            if "Restriction violated" in str(e):
                return "Previous not allowed on this device/context"
            return f"Spotify error: {e}"
        except Exception as e:
            return f"Spotify error: {e}"

    def volume_up(self, step=10):
        device = self._get_device()
        block = self._device_block_message(device)
        if block:
            return block
        if not device.get("supports_volume", False):
            return "This device does not support API volume"
        try:
            current_volume = device.get("volume_percent") or 0
            new_volume = min(100, current_volume + step)
            self.sp.volume(new_volume, device_id=device["id"])
            self._device["volume_percent"] = new_volume  # keep cache in sync
            return f"Volume: {new_volume}%"
        except spotipy.SpotifyException as e:
            self._device = None
            if "Cannot control device volume" in str(e):
                return "This device does not support API volume"
            return f"Spotify error: {e}"
        except Exception as e:
            return f"Spotify error: {e}"

    def volume_down(self, step=10):
        device = self._get_device()
        block = self._device_block_message(device)
        if block:
            return block
        if not device.get("supports_volume", False):
            return "This device does not support API volume"
        try:
            current_volume = device.get("volume_percent") or 0
            new_volume = max(0, current_volume - step)
            self.sp.volume(new_volume, device_id=device["id"])
            self._device["volume_percent"] = new_volume  # keep cache in sync
            return f"Volume: {new_volume}%"
        except spotipy.SpotifyException as e:
            self._device = None
            if "Cannot control device volume" in str(e):
                return "This device does not support API volume"
            return f"Spotify error: {e}"
        except Exception as e:
            return f"Spotify error: {e}"

    def get_current_track(self):
        try:
            playback = self.sp.current_playback()
            if not playback or not playback.get("item"):
                return ""
            track_name = playback["item"]["name"]
            artist_name = playback["item"]["artists"][0]["name"]
            return f"{track_name} - {artist_name}"
        except Exception:
            return ""
