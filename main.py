# main.py
# Raspberry Pi Spotify gesture controller.
# Includes camera, hand gesture recognition, Spotify controls,
# and optional hologram/body visualizer mode.

import json
import time
from pathlib import Path

import cv2

from camera.capture import CameraCapture
from vision.hand_tracker import HandTracker
from vision.gesture_classifier import GestureClassifier
from vision.pose_visualizer import PoseVisualizer
from utils.cooldown import Cooldown
from spotify.controller import SpotifyController
from utils.gesture_stability import GestureStability
from ui.overlay import draw_overlay, draw_hologram_status


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

    if not camera.is_opened():
        print("Could not open camera")
        return

    current_gesture = "No hand"
    current_action = "Waiting..."
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

    print("Project started.")
    print("Press Q to quit.")
    print("Press H to turn hologram on/off.")

    try:
        while True:
            ret, frame = camera.read_frame()

            if not ret:
                print("Could not read frame")
                break

            frame_count += 1

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

            if detected_gesture:
                current_gesture = detected_gesture
                stable_gesture = stability.update(detected_gesture)

                if stable_gesture and cooldown.ready():
                    mapped_action = gesture_map.get(stable_gesture, "no_action")
                    current_action = execute_action(mapped_action, spotify)
                    print(f"Gesture: {stable_gesture} -> Action: {current_action}")
                    stability.reset()
                    # Force track refresh after actions that change the song.
                    if mapped_action in ("next_track", "previous_track", "play"):
                        last_track_time = 0.0

            else:
                current_gesture = "No hand"
                stability.reset()

            # Refresh the now-playing track on a timer.
            now = time.time()
            if now - last_track_time >= track_refresh_interval:
                current_track = spotify.get_current_track()
                last_track_time = now

            frame = draw_overlay(frame, current_gesture, current_action, current_track)
            frame = draw_hologram_status(frame, hologram_enabled)

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
