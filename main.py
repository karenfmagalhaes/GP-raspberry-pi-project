import json
import time
from pathlib import Path

import cv2

from utils.hold_detector import HoldDetector
from camera.capture import CameraCapture
from vision.hand_tracker import HandTracker
from vision.gesture_classifier import GestureClassifier
from vision.pose_visualizer import PoseVisualizer
from utils.cooldown import Cooldown
from spotify.controller import SpotifyController
from utils.gesture_stability import GestureStability
from ui.hologram_display import HologramDisplay


_GESTURE_MESSAGES = {
    "open_palm":     "Playing.",
    "fist":          "Paused.",
    "three_fingers": "Next track.",
    "peace":         "Previous track.",
    "thumbs_up":     "Volume up.",
    "thumbs_down":   "Volume down.",
}


def _load_gesture_map():
    path = Path(__file__).resolve().parent / "config" / "gestures.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _execute(mapped_action, spotify):
    if mapped_action == "play":
        return spotify.play()
    if mapped_action == "pause":
        return spotify.pause()
    if mapped_action == "next_track":
        return spotify.next_track()
    if mapped_action == "previous_track":
        return spotify.previous_track()
    if mapped_action == "volume_up":
        return spotify.volume_up()
    if mapped_action == "volume_down":
        return spotify.volume_down()
    return "No action mapped"


def _is_error(result):
    r = result.lower()
    return any(k in r for k in ("error", "no active", "not allowed",
                                "restricted", "does not support"))


def main():
    camera      = CameraCapture(width=640, height=480, framerate=12, rotation=90, autofocus=True)
    tracker     = HandTracker()
    classifier  = GestureClassifier()
    pose_vis    = PoseVisualizer()
    cooldown    = Cooldown(delay=1.0)
    stability   = GestureStability(required_frames=3)
    spotify     = SpotifyController()
    gesture_map = _load_gesture_map()

    # Pygame hologram window: camera shows as a ghost background.
    display = HologramDisplay(fps=12, show_camera=True)

    gesture_active   = False
    last_active_time = 0.0
    ACTIVE_TIMEOUT   = 10.0
    wake_detector    = HoldDetector("wake", hold_seconds=1.5)

    if not camera.is_opened():
        print("[HoloBeat] Could not open camera.")
        display.close()
        return

    current_gesture = "No hand"
    current_track   = ""
    last_track_time = 0.0

    # Body hologram is OFF by default — press H to enable.
    # Pose runs every 2 frames (6 updates/s at 12 FPS) for smoother hologram.
    body_on             = False
    pose_every_n_frames = 2
    frame_count         = 0
    last_pose_results   = None

    # States: standby | ready | executing | error
    state        = "standby"
    message      = "Hold one finger up to activate."
    action_until = 0.0

    print("HoloBeat  —  gesture-controlled Spotify interface")
    print("  H  toggle hologram body  (transforms camera into glowing figure)")
    print("  Q  quit")
    print("  Hold index finger up for 1.5 s to activate gesture controls.")

    try:
        while True:
            ret, frame = camera.read_frame()
            if not ret:
                print("[HoloBeat] Camera read failed.")
                break

            frame_count += 1
            now   = time.time()
            frame = cv2.flip(frame, 1)

            hand_results = tracker.process(frame)

            # Body hologram: update pose every N frames, apply transform every frame.
            if body_on:
                if frame_count % pose_every_n_frames == 0:
                    last_pose_results = pose_vis.process(frame)
                # draw_hologram_body handles missing results gracefully
                # (returns darkened background with grid/corners only).
                frame = pose_vis.draw_hologram_body(frame, last_pose_results, state)

            # Classify gesture; only draw raw landmarks when hologram is OFF
            # (hologram body provides its own hand visualization).
            detected = None
            if hand_results.multi_hand_landmarks:
                for lm in hand_results.multi_hand_landmarks:
                    if not body_on:
                        tracker.draw_landmarks(frame, lm)
                    detected = classifier.classify(lm)

            # ----------------------------------------------------------------
            # Auto-lock after inactivity
            # ----------------------------------------------------------------
            if gesture_active and now - last_active_time > ACTIVE_TIMEOUT:
                gesture_active = False
                state          = "standby"
                message        = "Gesture controls locked again."
                action_until   = 0.0
                wake_detector.reset()
                stability.reset()
                print("[HoloBeat] Standby — timeout")

            # ----------------------------------------------------------------
            # Gesture processing
            # ----------------------------------------------------------------
            if detected:
                current_gesture = detected

                if not gesture_active:
                    if wake_detector.update(detected):
                        gesture_active   = True
                        last_active_time = now
                        state            = "ready"
                        message          = "Gesture controls active."
                        action_until     = 0.0
                        wake_detector.reset()
                        stability.reset()
                        cooldown.reset()
                        print("[HoloBeat] Controls active")
                    elif state != "error":
                        state = "standby"
                        if detected == "wake" and wake_detector.start_time is not None:
                            message = "Hold still..."
                        else:
                            message = "Hold one finger up to activate."

                else:
                    if detected == "wake":
                        last_active_time = now   # keep controls alive
                    else:
                        stable = stability.update(detected)
                        if stable and cooldown.ready():
                            mapped = gesture_map.get(stable, "no_action")
                            result = _execute(mapped, spotify)

                            if _is_error(result):
                                state        = "error"
                                message      = result
                                action_until = now + 4.0
                            else:
                                state        = "executing"
                                message      = _GESTURE_MESSAGES.get(stable, "Done.")
                                action_until = now + 3.0

                            print(f"[HoloBeat] {stable} -> {result}")
                            last_active_time = now
                            stability.reset()
                            cooldown.reset()

                            if mapped in ("next_track", "previous_track", "play"):
                                last_track_time = 0.0

            else:
                current_gesture = "No hand"
                stability.reset()
                wake_detector.reset()

                if not gesture_active and state not in ("executing", "error", "ready"):
                    state   = "standby"
                    message = "Hold one finger up to activate."

            # ----------------------------------------------------------------
            # Revert executing / error back to idle
            # ----------------------------------------------------------------
            if state in ("executing", "error") and now > action_until:
                if gesture_active:
                    state   = "ready"
                    message = "Gesture controls active."
                else:
                    state   = "standby"
                    message = "Hold one finger up to activate."

            # ----------------------------------------------------------------
            # Refresh now-playing track
            # ----------------------------------------------------------------
            if now - last_track_time >= 5.0:
                current_track   = spotify.get_current_track()
                last_track_time = now

            # Wake hold progress (0.0 – 1.0) for the arc around the orb.
            wake_progress = 0.0
            if wake_detector.start_time is not None and not gesture_active:
                wake_progress = min(
                    1.0,
                    (now - wake_detector.start_time) / wake_detector.hold_seconds,
                )

            # ----------------------------------------------------------------
            # Render — pygame hologram display
            # ----------------------------------------------------------------
            display.draw(
                frame,
                state,
                message,
                gesture=current_gesture,
                track=current_track,
                body_on=body_on,
                wake_progress=wake_progress,
            )

            # ----------------------------------------------------------------
            # Input — handled by pygame event loop
            # ----------------------------------------------------------------
            cmd = display.poll()
            if cmd == "quit":
                break
            if cmd == "toggle_body":
                body_on = not body_on
                print(f"[HoloBeat] Body skeleton {'ON' if body_on else 'OFF'}")

    finally:
        camera.release()
        tracker.close()
        pose_vis.close()
        display.close()
        print("[HoloBeat] Closed.")


if __name__ == "__main__":
    main()
