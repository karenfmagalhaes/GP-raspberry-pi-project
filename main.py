import json
import cv2

from camera.capture import CameraCapture
from vision.hand_tracker import HandTracker
from vision.gesture_classifier import GestureClassifier
from utils.cooldown import Cooldown
from spotify.controller import SpotifyController
from utils.gesture_stability import GestureStability
from ui.overlay import draw_overlay


def load_gesture_map():
    with open("config/gestures.json", "r", encoding="utf-8") as file:
        return json.load(file)


def execute_action(mapped_action, spotify):
    if mapped_action == "play":
        return spotify.play()
    elif mapped_action == "pause":
        return spotify.pause()
    elif mapped_action == "next_track":
        return spotify.next_track()
    elif mapped_action == "previous_track":
        return spotify.previous_track()
    elif mapped_action == "volume_up":
        return spotify.volume_up()
    elif mapped_action == "volume_down":
        return spotify.volume_down()
    else:
        return "no_action"


def main():
    camera = CameraCapture()
    tracker = HandTracker()
    classifier = GestureClassifier()
    cooldown = Cooldown(delay=2.0)
    stability = GestureStability(required_frames=6)
    spotify = SpotifyController()

    gesture_map = load_gesture_map()

    if not camera.is_opened():
        print("Could not open webcam")
        return

    current_gesture = "No hand"
    current_action = "Waiting..."

    while True:
        ret, frame = camera.read_frame()
        if not ret:
            print("Could not read frame")
            break

        frame = cv2.flip(frame, 1)
        results = tracker.process(frame)

        detected_gesture = None

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                tracker.draw_landmarks(frame, hand_landmarks)

                gesture = classifier.classify(hand_landmarks)
                detected_gesture = gesture

        if detected_gesture:
            current_gesture = detected_gesture
            stable_gesture = stability.update(detected_gesture)

            if stable_gesture and cooldown.ready():
                mapped_action = gesture_map.get(stable_gesture, "no_action")
                current_action = execute_action(mapped_action, spotify)
        else:
            current_gesture = "No hand"
            stability.update(None)

        frame = draw_overlay(frame, current_gesture, current_action)

        cv2.imshow("Gesture Spotify Player", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()