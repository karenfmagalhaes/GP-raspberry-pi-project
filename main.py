import json
import time
from pathlib import Path

import cv2

from utils.hold_detector import HoldDetector
from camera.capture import CameraCapture
from vision.hand_tracker import HandTracker
from vision.gesture_classifier import GestureClassifier
from utils.cooldown import Cooldown
from spotify.controller import SpotifyController
from utils.gesture_stability import GestureStability
from ui.hologram_display import HologramDisplay


_GESTURE_MESSAGES = {
    "open_palm": "Playing.",
    "fist": "Paused.",
    "three_fingers": "Next track.",
    "peace": "Previous track.",
    "thumbs_up": "Volume up.",
    "thumbs_down": "Volume down.",
}


def _load_gesture_map():
    path = Path(__file__).resolve().parent / "config" / "gestures.json"

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


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
    result = result.lower()

    error_words = (
        "error",
        "no active",
        "not allowed",
        "restricted",
        "does not support",
        "could not",
    )

    return any(word in result for word in error_words)


def main():
    # Camera is used for gesture input only.
    # The hologram is now the interface, not the body skeleton.
    camera = CameraCapture(
        width=480,
        height=360,
        framerate=10,
        rotation=0,
        autofocus=True,
    )

    tracker = HandTracker()
    classifier = GestureClassifier()
    cooldown = Cooldown(delay=1.0)
    stability = GestureStability(required_frames=3)
    spotify = SpotifyController()
    gesture_map = _load_gesture_map()

    # Hologram interface window.
    display = HologramDisplay(fps=12, show_camera=True)

    # Wake mode: user must hold one finger up first.
    gesture_active = False
    last_active_time = 0.0
    active_timeout = 10.0
    wake_detector = HoldDetector("wake", hold_seconds=1.5)

    if not camera.is_opened():
        print("[HoloBeat] Could not open camera.")
        display.close()
        return

    current_gesture = "No hand"
    current_track = ""
    last_track_time = 0.0

    # Interface states:
    # standby | ready | executing | error
    state = "standby"
    message = "Hold one finger up to activate."
    action_until = 0.0

    print("HoloBeat — gesture-controlled Spotify hologram interface")
    print("Q = quit")
    print("H = toggle camera background")
    print("Hold one finger up for 1.5 seconds to activate gesture controls.")

    try:
        while True:
            ret, frame = camera.read_frame()

            if not ret:
                print("[HoloBeat] Camera read failed.")
                break

            now = time.time()

            # Mirror image so gestures feel natural.
            frame = cv2.flip(frame, 1)

            # Hand tracking only. No body pose processing.
            hand_results = tracker.process(frame)

            detected = None

            if hand_results.multi_hand_landmarks:
                for hand_landmarks in hand_results.multi_hand_landmarks:
                    detected = classifier.classify(hand_landmarks)

            # ------------------------------------------------------------
            # Auto-lock after inactivity
            # ------------------------------------------------------------
            if gesture_active and now - last_active_time > active_timeout:
                gesture_active = False
                state = "standby"
                message = "Gesture controls locked again."
                action_until = 0.0
                wake_detector.reset()
                stability.reset()
                print("[HoloBeat] Standby — timeout")

            # ------------------------------------------------------------
            # Gesture processing
            # ------------------------------------------------------------
            if detected:
                current_gesture = detected

                if not gesture_active:
                    if wake_detector.update(detected):
                        gesture_active = True
                        last_active_time = now
                        state = "ready"
                        message = "Gesture controls active."
                        action_until = 0.0

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
                        # Keep controls alive.
                        last_active_time = now

                    else:
                        stable = stability.update(detected)

                        if stable and cooldown.ready():
                            mapped_action = gesture_map.get(stable, "no_action")
                            result = _execute(mapped_action, spotify)

                            if _is_error(result):
                                state = "error"
                                message = result
                                action_until = now + 4.0

                            else:
                                state = "executing"
                                message = _GESTURE_MESSAGES.get(stable, "Done.")
                                action_until = now + 3.0

                            print(f"[HoloBeat] {stable} -> {result}")

                            last_active_time = now
                            stability.reset()
                            cooldown.reset()

                            if mapped_action in ("next_track", "previous_track", "play"):
                                last_track_time = 0.0

            else:
                current_gesture = "No hand"
                stability.reset()
                wake_detector.reset()

                if not gesture_active and state not in ("executing", "error", "ready"):
                    state = "standby"
                    message = "Hold one finger up to activate."

            # ------------------------------------------------------------
            # Return from executing/error state
            # ------------------------------------------------------------
            if state in ("executing", "error") and now > action_until:
                if gesture_active:
                    state = "ready"
                    message = "Gesture controls active."
                else:
                    state = "standby"
                    message = "Hold one finger up to activate."

            # ------------------------------------------------------------
            # Refresh current Spotify track every 5 seconds
            # ------------------------------------------------------------
            if now - last_track_time >= 5.0:
                current_track = spotify.get_current_track()
                last_track_time = now

            # Wake progress for the ring animation.
            wake_progress = 0.0

            if wake_detector.start_time is not None and not gesture_active:
                wake_progress = min(
                    1.0,
                    (now - wake_detector.start_time) / wake_detector.hold_seconds,
                )

            # ------------------------------------------------------------
            # Render hologram interface
            # ------------------------------------------------------------
            display.draw(
                frame,
                state,
                message,
                gesture=current_gesture,
                track=current_track,
                body_on=False,
                wake_progress=wake_progress,
            )

            # ------------------------------------------------------------
            # Keyboard input from pygame window
            # ------------------------------------------------------------
            command = display.poll()

            if command == "quit":
                break

            if command == "toggle_body":
                display.show_camera = not display.show_camera
                print(
                    f"[HoloBeat] Camera background "
                    f"{'ON' if display.show_camera else 'OFF'}"
                )

    finally:
        camera.release()
        tracker.close()
        display.close()
        print("[HoloBeat] Closed.")


if __name__ == "__main__":
    main()
