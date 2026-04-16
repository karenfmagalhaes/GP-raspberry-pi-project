import spotipy
from spotify.auth import get_spotify_auth


class SpotifyController:
    def __init__(self):
        self.sp = spotipy.Spotify(auth_manager=get_spotify_auth())

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

        if devices:
            return devices[0]

        return None

    def get_active_device_id(self):
        device = self.get_active_device()
        return device.get("id") if device else None

    def device_block_message(self, device):
        if not device:
            return "No active device"
        if device.get("is_restricted", False):
            return "This Spotify device is restricted"
        return None

    def play_pause(self):
        try:
            playback = self.sp.current_playback()
            device = self.get_active_device()

            block = self.device_block_message(device)
            if block:
                return block

            if playback and playback.get("is_playing"):
                self.sp.pause_playback(device_id=device["id"])
                return "Paused"
            else:
                self.sp.start_playback(device_id=device["id"])
                return "Playing"

        except Exception as e:
            return f"Spotify error: {e}"

    def play(self):
        try:
            device = self.get_active_device()

            block = self.device_block_message(device)
            if block:
                return block

            self.sp.start_playback(device_id=device["id"])
            return "Playing"

        except Exception as e:
            return f"Spotify error: {e}"

    def pause(self):
        try:
            device = self.get_active_device()

            block = self.device_block_message(device)
            if block:
                return block

            self.sp.pause_playback(device_id=device["id"])
            return "Paused"

        except Exception as e:
            return f"Spotify error: {e}"

    def next_track(self):
        try:
            device = self.get_active_device()

            block = self.device_block_message(device)
            if block:
                return block

            self.sp.next_track(device_id=device["id"])
            return "Next track"

        except Exception as e:
            if "Restriction violated" in str(e):
                return "Next not allowed on this device/context"
            return f"Spotify error: {e}"

    def previous_track(self):
        try:
            device = self.get_active_device()

            block = self.device_block_message(device)
            if block:
                return block

            self.sp.previous_track(device_id=device["id"])
            return "Previous track"

        except Exception as e:
            if "Restriction violated" in str(e):
                return "Previous not allowed on this device/context"
            return f"Spotify error: {e}"

    def volume_up(self, step=10):
        try:
            device = self.get_active_device()

            block = self.device_block_message(device)
            if block:
                return block

            if not device.get("supports_volume", False):
                return "This device does not support API volume"

            current_volume = device.get("volume_percent", 0)
            new_volume = min(100, current_volume + step)

            self.sp.volume(new_volume, device_id=device["id"])
            return f"Volume: {new_volume}%"

        except Exception as e:
            if "Cannot control device volume" in str(e):
                return "This device does not support API volume"
            return f"Spotify error: {e}"

    def volume_down(self, step=10):
        try:
            device = self.get_active_device()

            block = self.device_block_message(device)
            if block:
                return block

            if not device.get("supports_volume", False):
                return "This device does not support API volume"

            current_volume = device.get("volume_percent", 0)
            new_volume = max(0, current_volume - step)

            self.sp.volume(new_volume, device_id=device["id"])
            return f"Volume: {new_volume}%"

        except Exception as e:
            if "Cannot control device volume" in str(e):
                return "This device does not support API volume"
            return f"Spotify error: {e}"

    def get_current_track(self):
        try:
            playback = self.sp.current_playback()

            if not playback or not playback.get("item"):
                return "Nothing playing"

            track_name = playback["item"]["name"]
            artist_name = playback["item"]["artists"][0]["name"]

            return f"{track_name} - {artist_name}"

        except Exception as e:
            return f"Spotify error: {e}"