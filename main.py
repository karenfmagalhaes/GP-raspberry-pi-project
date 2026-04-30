# main.py
# Raspberry Pi Spotify gesture controller with Sendo virtual assistant.
# Includes camera, hand gesture recognition, Spotify controls,
# wake gesture activation, Spotify cooldown,
# and optional hologram/body visualizer mode.

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
from ui.overlay import draw_overlay, draw_hologram_status
from ui.virtual_assistant import draw_virtual_assistant


# Maps stable gestures to the Sendo assistant message shown on action.
GESTURE_MESSAGES = {
    "open_palm":     "Playing your music.",
    "fist":          "Music paused.",
    "three_fingers": "Skipping to next track.",
    "peace":         "Going back one track.",
    "thumbs_up":     "Increasing volume.",
    "thumbs_down":   "Decreasing volume.",
}


def load_gesture_map():
    base_dir = Path(__file__).resolve().parent
    gestures_file = base_dir / "config" / "gestures.json"

    with open(gestures_file, "r", encoding="utf-8") as file:
        return json.load(file)


def execute_action(mapped_action, spotify):
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


def _is_error_result(result):
    r = result.lower()
    return (
        "error" in r
        or "no active" in r
        or "not allowed" in r
        or "restricted" in r
        or "does not support" in r
    )


def main():
    # Lower framerate helps reduce delay on Raspberry Pi.
    camera = CameraCapture(width=640, height=480, framerate=12, autofocus=True)

    tracker = HandTracker()
    classifier = GestureClassifier()
    pose_visualizer = PoseVisualizer()

    # Faster gesture reaction.
    cooldown = Cooldown(delay=1.0)
    stability = GestureStability(required_frames=3)

    spotify = SpotifyController()
    gesture_map = load_gesture_map()

    # ------------------------------------------------------------
    # Wake gesture settings
    # ------------------------------------------------------------
    gesture_controls_active = False
    last_active_time = 0.0

    ACTIVE_TIMEOUT = 10.0  # seconds before controls turn OFF again
    wake_detector = HoldDetector("wake", hold_seconds=1.5)

    if not camera.is_opened():
        print("Could not open camera")
        return

    current_gesture = "No hand"
    current_action = "Controls OFF - hold wake gesture"
    current_track = ""

    # Refresh "now playing" every 5 seconds; set to 0 to force an immediate first fetch.
    last_track_time = 0.0
    track_refresh_interval = 5.0

    # Hologram starts ON because it is part of your project idea.
    hologram_enabled = True

    # Process pose every few frames only to reduce delay.
    pose_every_n_frames = 3
    frame_count = 0
    last_pose_results = None

    # ------------------------------------------------------------
    # Sendo assistant state
    # ------------------------------------------------------------
    assistant_state   = "sleeping"
    assistant_message = "Hold one finger up to wake me."
    action_display_until = 0.0  # when to revert from action/error back to listening

    print("Project started.")
    print("Press Q to quit.")
    print("Press H to turn hologram on/off.")
    print("Gesture controls are OFF.")
    print("Hold the wake gesture to activate Spotify controls.")

    try:
        while True:
            ret, frame = camera.read_frame()

            if not ret:
                print("Could not read frame")
                break

            frame_count += 1
            now = time.time()

            # Mirror image, easier for gesture control.
            frame = cv2.flip(frame, 1)

            # Hand tracking runs every frame because gestures need fast response.
            hand_results = tracker.process(frame)

            # Hologram/body pose runs only every 3 frames to reduce delay.
            if hologram_enabled:
                if frame_count % pose_every_n_frames == 0:
                    last_pose_results = pose_visualizer.process(frame)

                if last_pose_results:
                    frame = pose_visualizer.draw_glow_pose(frame, last_pose_results)

            detected_gesture = None

            if hand_results.multi_hand_landmarks:
                for hand_landmarks in hand_results.multi_hand_landmarks:
                    tracker.draw_landmarks(frame, hand_landmarks)

                    gesture = classifier.classify(hand_landmarks)
                    detected_gesture = gesture

            # ------------------------------------------------------------
            # Auto-disable controls after inactivity
            # ------------------------------------------------------------
            if gesture_controls_active and now - last_active_time > ACTIVE_TIMEOUT:
                gesture_controls_active = False
                current_action = "Controls OFF - hold wake gesture"
                assistant_state   = "sleeping"
                assistant_message = "I am sleeping again."
                action_display_until = 0.0
                wake_detector.reset()
                stability.reset()
                print("[System] Gesture controls OFF - timeout")

            # ------------------------------------------------------------
            # Gesture detected
            # ------------------------------------------------------------
            if detected_gesture:
                current_gesture = detected_gesture

                # --------------------------------------------------------
                # If controls are OFF, only listen for wake gesture
                # --------------------------------------------------------
                if not gesture_controls_active:
                    if wake_detector.update(detected_gesture):
                        gesture_controls_active = True
                        last_active_time = now
                        current_action = "Controls ON - ready"
                        assistant_state   = "listening"
                        assistant_message = "I am listening. Show me a Spotify gesture."
                        action_display_until = 0.0
                        wake_detector.reset()
                        stability.reset()
                        cooldown.reset()
                        print("[System] Gesture controls ON")

                    else:
                        current_action = "Controls OFF - hold wake gesture"

                # --------------------------------------------------------
                # If controls are ON, allow normal Spotify gestures
                # --------------------------------------------------------
                else:
                    # Do not execute the wake gesture as a Spotify action.
                    if detected_gesture == "wake":
                        current_action = "Controls ON - ready"
                    else:
                        stable_gesture = stability.update(detected_gesture)

                        if stable_gesture and cooldown.ready():
                            mapped_action = gesture_map.get(stable_gesture, "no_action")
                            result = execute_action(mapped_action, spotify)
                            current_action = result

                            if _is_error_result(result):
                                assistant_state   = "error"
                                assistant_message = result
                                action_display_until = now + 4.0
                            else:
                                assistant_state   = "action"
                                assistant_message = GESTURE_MESSAGES.get(stable_gesture, "Done.")
                                action_display_until = now + 3.0

                            print(f"Gesture: {stable_gesture} -> Action: {result}")

                            last_active_time = now
                            stability.reset()
                            cooldown.reset()

                            # Force track refresh after actions that change the song.
                            if mapped_action in ("next_track", "previous_track", "play"):
                                last_track_time = 0.0

            # ------------------------------------------------------------
            # No hand detected
            # ------------------------------------------------------------
            else:
                current_gesture = "No hand"
                stability.reset()
                wake_detector.reset()

                if gesture_controls_active:
                    current_action = "Controls ON - waiting for gesture"
                else:
                    current_action = "Controls OFF - hold wake gesture"

            # ------------------------------------------------------------
            # Revert action/error display back to listening (or sleeping)
            # ------------------------------------------------------------
            if assistant_state in ("action", "error") and now > action_display_until:
                if gesture_controls_active:
                    assistant_state   = "listening"
                    assistant_message = "I am listening. Show me a Spotify gesture."
                else:
                    assistant_state   = "sleeping"
                    assistant_message = "Hold one finger up to wake me."

            # ------------------------------------------------------------
            # Refresh the now-playing track on a timer
            # ------------------------------------------------------------
            if now - last_track_time >= track_refresh_interval:
                current_track = spotify.get_current_track()
                last_track_time = now

            # ------------------------------------------------------------
            # Draw UI
            # ------------------------------------------------------------
            frame = draw_overlay(frame, current_gesture, current_action, current_track)
            frame = draw_hologram_status(frame, hologram_enabled)
            frame = draw_virtual_assistant(
                frame,
                assistant_state,
                assistant_message,
                gesture=current_gesture,
                action=current_action,
                track=current_track,
            )

            cv2.imshow("Gesture Spotify Player", frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            if key == ord("h"):
                hologram_enabled = not hologram_enabled
                print(f"Hologram mode: {'ON' if hologram_enabled else 'OFF'}")

    finally:
        camera.release()
        tracker.close()
        pose_visualizer.close()
        cv2.destroyAllWindows()
        print("Project closed.")


if __name__ == "__main__":
    main()
