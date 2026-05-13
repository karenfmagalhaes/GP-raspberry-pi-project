# main.py
# Runs the WaveBeat gesture-controlled Spotify interface.

import json
import time
from pathlib import Path

import cv2

from utils.hold_detector import HoldDetector
from utils.gesture_stability import GestureStability
from utils.cooldown import Cooldown
from camera.capture import CameraCapture
from vision.hand_tracker import HandTracker
from vision.gesture_classifier import GestureClassifier
from vision.motion_gesture_detector import MotionGestureDetector
from spotify.controller import SpotifyController
from ui.hologram_display import HologramDisplay


VOLUME_STEP = 5


_GESTURE_MESSAGES = {
    "open_palm": "Playing.",
    "fist": "Paused.",
    "one_finger_swipe_right": "Next track.",
    "one_finger_swipe_left": "Previous track.",
}


def _load_gesture_map():
    path = Path(__file__).resolve().parent / "config" / "gestures.json"

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _execute(mapped_action, spotify):
    dispatch = {
        "play": spotify.play,
        "pause": spotify.pause,
        "next_track": spotify.next_track,
        "previous_track": spotify.previous_track,
    }

    fn = dispatch.get(mapped_action)

    return fn() if fn else "No action mapped"


def _is_error(result):
    result = result.lower()

    return any(
        word in result
        for word in (
            "error",
            "no active",
            "not allowed",
            "restricted",
            "does not support",
            "could not",
        )
    )


def main():
    camera = CameraCapture(
        width=480,
        height=360,
        framerate=10,
        rotation=0,
        autofocus=True,
    )

    tracker = HandTracker()
    classifier = GestureClassifier()
    motion_detector = MotionGestureDetector()

    stability = GestureStability(required_frames=8)
    cooldown = Cooldown(delay=1.5)

    spotify = SpotifyController()
    gesture_map = _load_gesture_map()

    # Final hologram display.
    # Camera still detects gestures, but it is NOT shown as background.
    display = HologramDisplay(
        fps=12,
        show_camera=False,
        fullscreen=True,
        mirror_output=True,
    )

    gesture_active = False
    last_active_time = 0.0
    active_timeout = 10.0

    ok_detector = HoldDetector("ok", hold_seconds=1.5)

    last_static_fired = None

    volume_display = ""
    volume_display_until = 0.0

    if not camera.is_opened():
        print("[WaveBeat] Could not open camera.")
        display.close()
        return

    current_gesture = "No hand"
    executing_gesture = ""
    current_track = ""
    last_track_time = 0.0

    state = "standby"
    message = "Show OK sign to activate gestures."
    action_until = 0.0

    print("WaveBeat — gesture-controlled Spotify hologram interface")
    print("Q/ESC = quit | G = guide | M = mirror mode")
    print("Hold the OK sign for 1.5 seconds to activate gesture controls.")

    try:
        while True:
            ret, frame = camera.read_frame()

            if not ret or frame is None:
                print("[WaveBeat] Camera read failed.")
                break

            now = time.time()

            # Mirror camera frame so gestures feel natural.
            frame = cv2.flip(frame, 1)

            hand_results = tracker.process(frame)

            detected_static = None
            detected_motion = None

            if hand_results.multi_hand_landmarks:
                for hand_landmarks in hand_results.multi_hand_landmarks:
                    detected_static = classifier.classify(hand_landmarks)

                    if gesture_active:
                        detected_motion = motion_detector.update(
                            hand_landmarks,
                            detected_static,
                        )

                current_gesture = detected_static if detected_static else "hand"

                if detected_motion:
                    current_gesture = detected_motion

            else:
                current_gesture = "No hand"
                last_static_fired = None
                ok_detector.reset()
                motion_detector.reset()
                stability.reset()

                if not gesture_active and state not in ("executing", "error", "ready"):
                    state = "standby"
                    message = "Show OK sign to activate gestures."

            if gesture_active and now - last_active_time > active_timeout:
                gesture_active = False
                state = "standby"
                message = "Gesture controls locked again."
                action_until = 0.0
                executing_gesture = ""
                last_static_fired = None

                ok_detector.reset()
                motion_detector.reset()
                stability.reset()

                print("[WaveBeat] Standby — timeout")

            if hand_results.multi_hand_landmarks:
                if not gesture_active:
                    if ok_detector.update(detected_static):
                        gesture_active = True
                        last_active_time = now
                        state = "ready"
                        message = "Gesture controls active."
                        action_until = 0.0
                        executing_gesture = ""
                        last_static_fired = None

                        ok_detector.reset()
                        cooldown.reset()
                        motion_detector.reset()
                        stability.reset()

                        print("[WaveBeat] Controls active")

                    elif state != "error":
                        state = "standby"

                        if detected_static == "ok" and ok_detector.start_time is not None:
                            message = "Hold still..."
                        else:
                            message = "Show OK sign to activate gestures."

                else:
                    last_active_time = now

                    if detected_static != last_static_fired:
                        last_static_fired = None

                    # Priority 1: Volume gesture
                    if detected_motion in ("peace_move_up", "peace_move_down"):
                        is_up = detected_motion == "peace_move_up"

                        result = (
                            spotify.volume_up(step=VOLUME_STEP)
                            if is_up
                            else spotify.volume_down(step=VOLUME_STEP)
                        )

                        if _is_error(result):
                            state = "error"
                            message = result
                            executing_gesture = detected_motion
                            action_until = now + 4.0

                        else:
                            state = "executing"
                            message = result
                            executing_gesture = detected_motion
                            action_until = now + 2.5

                            # This appears under the big VOL+/VOL- action.
                            volume_display = result
                            volume_display_until = now + 2.5

                        stability.reset()

                        print(f"[WaveBeat] {detected_motion} -> {result}")

                    # Priority 2: Swipe gesture
                    elif detected_motion and cooldown.ready():
                        mapped_action = gesture_map.get(detected_motion, "no_action")
                        result = _execute(mapped_action, spotify)

                        if _is_error(result):
                            state = "error"
                            message = result
                            executing_gesture = detected_motion
                            action_until = now + 4.0

                        else:
                            state = "executing"
                            message = _GESTURE_MESSAGES.get(detected_motion, "Done.")
                            executing_gesture = detected_motion
                            action_until = now + 3.0

                        stability.reset()
                        last_static_fired = None

                        print(f"[WaveBeat] {detected_motion} -> {result}")

                    # Priority 3: Static hold gesture open_palm / fist
                    elif detected_static in ("open_palm", "fist"):
                        if last_static_fired == detected_static:
                            stability.reset()

                        else:
                            stable = stability.update(detected_static)

                            if stable and cooldown.ready():
                                mapped_action = gesture_map.get(stable, "no_action")
                                result = _execute(mapped_action, spotify)

                                if _is_error(result):
                                    state = "error"
                                    message = result
                                    executing_gesture = stable
                                    action_until = now + 4.0

                                else:
                                    state = "executing"
                                    message = _GESTURE_MESSAGES.get(stable, "Done.")
                                    executing_gesture = stable
                                    action_until = now + 3.0

                                last_static_fired = detected_static
                                stability.reset()

                                print(f"[WaveBeat] {stable} -> {result}")

                    else:
                        stability.reset()
                        last_static_fired = None

            if state in ("executing", "error") and now > action_until:
                executing_gesture = ""

                if gesture_active:
                    state = "ready"
                    message = "Gesture controls active."
                else:
                    state = "standby"
                    message = "Show OK sign to activate gestures."

            if now - last_track_time >= 5.0:
                current_track = spotify.get_current_track()
                last_track_time = now

            wake_progress = 0.0

            if ok_detector.start_time is not None and not gesture_active:
                wake_progress = min(
                    1.0,
                    (now - ok_detector.start_time) / ok_detector.hold_seconds,
                )

            display_gesture = (
                executing_gesture
                if state in ("executing", "error") and executing_gesture
                else current_gesture
            )

            # IMPORTANT:
            # The NOW PLAYING box always shows the song.
            # Volume is NOT sent to the NOW PLAYING box anymore.
            track_display = current_track

            # If volume action is active, show volume only in the centre message.
            center_message = (
                volume_display
                if now < volume_display_until
                else message
            )

            display.draw(
                frame,
                state,
                center_message,
                gesture=display_gesture,
                track=track_display,
                camera_on=False,
                wake_progress=wake_progress,
            )

            command = display.poll()

            if command == "quit":
                break

    finally:
        camera.release()
        tracker.close()
        display.close()
        print("[WaveBeat] Closed.")


if __name__ == "__main__":
    main()
