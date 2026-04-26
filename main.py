# main.py
# Main program for the Raspberry Pi Spotify gesture controller.
# It uses the camera, hand gesture detection, body glow visualizer, and Spotify controls.

import json
from pathlib import Path

import cv2

from camera.capture import CameraCapture
from vision.hand_tracker import HandTracker
from vision.gesture_classifier import GestureClassifier
from vision.pose_visualizer import PoseVisualizer
from utils.cooldown import Cooldown
from spotify.controller import SpotifyController
from utils.gesture_stability import GestureStability
from ui.overlay import draw_overlay


def load_gesture_map():
    # Finds config/gestures.json safely, even if the program is run from another folder.
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
    camera = CameraCapture()
    tracker = HandTracker()
    classifier = GestureClassifier()
    pose_visualizer = PoseVisualizer()
    cooldown = Cooldown(delay=2.0)
    stability = GestureStability(required_frames=6)
    spotify = SpotifyController()

    gesture_map = load_gesture_map()

    if not camera.is_opened():
        print("Could not open camera")
        return

    current_gesture = "No hand"
    current_action = "Waiting..."

    print("Project started. Press Q to quit.")

    try:
        while True:
            ret, frame = camera.read_frame()

            if not ret:
                print("Could not read frame")
                break

            # Mirror image, easier for gesture control.
            frame = cv2.flip(frame, 1)

            # Process pose and hand detection on the clean frame first.
            pose_results = pose_visualizer.process(frame)
            hand_results = tracker.process(frame)

            # Draw body glow effect.
            frame = pose_visualizer.draw_glow_pose(frame, pose_results)

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

            else:
                current_gesture = "No hand"
                stability.reset()

            frame = draw_overlay(frame, current_gesture, current_action)

            cv2.imshow("Gesture Spotify Player", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        camera.release()
        tracker.close()
        pose_visualizer.close()
        cv2.destroyAllWindows()
        print("Project closed.")


if __name__ == "__main__":
    main()
