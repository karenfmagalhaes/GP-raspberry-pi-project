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

# Set False on Raspberry Pi with real Spotify credentials.
TEST_MODE = False

VOLUME_STEP = 5   # percent per volume gesture (controller default is 10)

_GESTURE_MESSAGES = {
    "open_palm":              "Playing.",
    "fist":                   "Paused.",
    "one_finger_swipe_right": "Next track.",
    "one_finger_swipe_left":  "Previous track.",
    "peace_move_up":          "Volume up.",
    "peace_move_down":        "Volume down.",
    "rock":                   "Background view toggled.",
}


def _load_gesture_map():
    path = Path(__file__).resolve().parent / "config" / "gestures.json"
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _execute(mapped_action, spotify):
    if TEST_MODE:
        return f"TEST MODE: {mapped_action}"
    dispatch = {
        "play":           spotify.play,
        "pause":          spotify.pause,
        "next_track":     spotify.next_track,
        "previous_track": spotify.previous_track,
        "volume_up":      lambda: spotify.volume_up(step=VOLUME_STEP),
        "volume_down":    lambda: spotify.volume_down(step=VOLUME_STEP),
    }
    fn = dispatch.get(mapped_action)
    return fn() if fn else "No action mapped"


def _is_error(result):
    result = result.lower()
    return any(
        w in result
        for w in ("error", "no active", "not allowed", "restricted",
                  "does not support", "could not")
    )


def main():
    camera = CameraCapture(
        width=480,
        height=360,
        framerate=10,
        rotation=0,
        autofocus=True,
    )

    tracker         = HandTracker()
    classifier      = GestureClassifier()
    motion_detector = MotionGestureDetector()
    # GestureStability requires the same shape for 8 consecutive frames (~0.8 s
    # at 10 fps) before a static hold gesture (open_palm / fist) can fire.
    stability       = GestureStability(required_frames=8)
    # Cooldown enforces a minimum gap between any two Spotify actions.
    # ready() stamps the trigger time itself — do NOT call reset() after an
    # action or the cooldown is immediately undone.
    cooldown        = Cooldown(delay=1.5)
    spotify         = None if TEST_MODE else SpotifyController()
    gesture_map     = _load_gesture_map()

    display = HologramDisplay(fps=12, show_camera=True)

    gesture_active   = False
    last_active_time = 0.0
    active_timeout   = 10.0
    ok_detector      = HoldDetector("ok", hold_seconds=1.5)

    # Rock hold + cooldown — enforced here, not in gesture_classifier.
    rock_start         = None
    rock_last_fired    = 0.0
    rock_hold_seconds  = 0.8
    rock_cooldown_secs = 2.0

    # Release-to-trigger for open_palm / fist.
    # Stores the last static gesture that fired; same shape is blocked until
    # the user changes or removes their hand.
    last_static_fired = None

    # Volume mode — peace zone baseline approach.
    test_volume          = 50    # TEST_MODE simulated volume (0–100 %)
    volume_display       = ""    # "Volume: XX%" shown in the track area
    volume_display_until = 0.0

    if not camera.is_opened():
        print("[WaveBeat] Could not open camera.")
        display.close()
        return

    current_gesture   = "No hand"
    executing_gesture = ""   # used for the action animation during executing state
    current_track     = ""
    last_track_time   = 0.0

    state        = "standby"
    message      = "Show OK sign to activate gestures."
    action_until = 0.0

    print("WaveBeat — gesture-controlled Spotify hologram interface")
    print("Q = quit | H = toggle camera background | G = gesture guide")
    print("Hold the OK sign for 1.5 seconds to activate gesture controls.")

    try:
        while True:
            ret, frame = camera.read_frame()

            if not ret:
                print("[WaveBeat] Camera read failed.")
                break

            now = time.time()

            # Mirror so gestures feel natural.
            frame = cv2.flip(frame, 1)

            hand_results = tracker.process(frame)

            detected_static = None
            detected_motion = None

            # ----------------------------------------------------------------
            # Hand tracking
            # ----------------------------------------------------------------
            if hand_results.multi_hand_landmarks:
                for hand_landmarks in hand_results.multi_hand_landmarks:
                    detected_static = classifier.classify(hand_landmarks)
                    if gesture_active:
                        # Motion detector requires the current shape to gate
                        # which combination gesture it checks.
                        detected_motion = motion_detector.update(
                            hand_landmarks, detected_static
                        )

                # Display: prefer a motion event name, else the static shape.
                current_gesture = detected_static if detected_static else "hand"
                if detected_motion:
                    current_gesture = detected_motion

                # Reset rock hold timer when the user is not showing rock.
                if detected_static != "rock":
                    rock_start = None

            else:
                # No hand in frame — reset all transient detectors.
                current_gesture   = "No hand"
                last_static_fired = None
                ok_detector.reset()
                motion_detector.reset()
                stability.reset()
                rock_start = None

                if not gesture_active and state not in ("executing", "error", "ready"):
                    state   = "standby"
                    message = "Show OK sign to activate gestures."

            # ----------------------------------------------------------------
            # Auto-lock after inactivity
            # ----------------------------------------------------------------
            if gesture_active and now - last_active_time > active_timeout:
                gesture_active    = False
                state             = "standby"
                message           = "Gesture controls locked again."
                action_until      = 0.0
                executing_gesture = ""
                last_static_fired = None
                ok_detector.reset()
                motion_detector.reset()
                stability.reset()
                print("[WaveBeat] Standby — timeout")

            # ----------------------------------------------------------------
            # Gesture processing
            # ----------------------------------------------------------------
            if hand_results.multi_hand_landmarks:

                if not gesture_active:
                    # ---- Standby: only the OK sign activates controls ----
                    if ok_detector.update(detected_static):
                        gesture_active    = True
                        last_active_time  = now
                        state             = "ready"
                        message           = "Gesture controls active."
                        action_until      = 0.0
                        executing_gesture = ""
                        last_static_fired = None
                        ok_detector.reset()
                        cooldown.reset()   # allow first action immediately
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
                    # ---- Ready: process Spotify and system gestures ----

                    # Any visible hand keeps the active timer alive.
                    last_active_time = now

                    # Any gesture change clears the release-to-trigger block.
                    if detected_static != last_static_fired:
                        last_static_fired = None

                    # -- Priority 1: Rock (system gesture) --
                    # Must be held for rock_hold_seconds.
                    # A 2-second cooldown prevents accidental double-toggles.
                    # rock_start resets to None after each fire, so the user
                    # must fully re-show rock to toggle again.
                    if detected_static == "rock":
                        if rock_start is None:
                            rock_start = now

                        rock_elapsed = now - rock_start
                        rock_ready   = (
                            rock_elapsed >= rock_hold_seconds
                            and now - rock_last_fired >= rock_cooldown_secs
                        )

                        if rock_ready:
                            display.show_camera = not display.show_camera
                            rock_last_fired     = now
                            rock_start          = None   # must re-hold to fire again
                            state             = "executing"
                            message           = _GESTURE_MESSAGES["rock"]
                            executing_gesture = "rock"
                            action_until      = now + 2.0
                            print(
                                f"[WaveBeat] rock -> camera "
                                f"{'ON' if display.show_camera else 'OFF'}"
                            )
                        elif state == "ready":
                            message = "Hold rock gesture..."

                    # -- Priority 2a: Volume (peace zone) --
                    # The detector manages baseline + repeat timing internally so
                    # volume bypasses the main cooldown and can fire every second.
                    elif detected_motion in ("peace_move_up", "peace_move_down"):
                        is_up = detected_motion == "peace_move_up"
                        if TEST_MODE:
                            if is_up:
                                test_volume = min(100, test_volume + VOLUME_STEP)
                            else:
                                test_volume = max(0, test_volume - VOLUME_STEP)
                            result = f"Volume: {test_volume}%"
                        else:
                            result = (spotify.volume_up(step=VOLUME_STEP) if is_up
                                      else spotify.volume_down(step=VOLUME_STEP))

                        if _is_error(result):
                            state             = "error"
                            message           = result
                            executing_gesture = detected_motion
                            action_until      = now + 4.0
                        else:
                            state                = "executing"
                            message              = result   # "Volume: 45%"
                            executing_gesture    = detected_motion
                            action_until         = now + 2.5
                            volume_display       = result
                            volume_display_until = now + 2.5

                        stability.reset()
                        print(f"[WaveBeat] {detected_motion} -> {result}")

                    # -- Priority 2b: Swipe (one_finger) — main cooldown applies --
                    # Motion wins over a static hold — stability resets so a
                    # hand returning to still after a swipe must re-build before
                    # play can fire.
                    elif detected_motion and cooldown.ready():
                        mapped_action = gesture_map.get(detected_motion, "no_action")
                        result        = _execute(mapped_action, spotify)

                        if _is_error(result):
                            state             = "error"
                            message           = result
                            executing_gesture = detected_motion
                            action_until      = now + 4.0
                        else:
                            state             = "executing"
                            message           = _GESTURE_MESSAGES.get(detected_motion, "Done.")
                            executing_gesture = detected_motion
                            action_until      = now + 3.0

                        stability.reset()
                        last_static_fired = None
                        print(f"[WaveBeat] {detected_motion} -> {result}")
                        # Do NOT call cooldown.reset() — ready() already stamped it.

                    # -- Priority 3: Static hold gesture (open_palm / fist) --
                    # Requires the same shape for 8 consecutive frames (~0.8 s).
                    # Release-to-trigger: the same gesture cannot fire again until
                    # the user changes hand shape or removes their hand.
                    elif detected_static in ("open_palm", "fist"):
                        if last_static_fired == detected_static:
                            # Same gesture still held after firing — block re-trigger.
                            stability.reset()
                        else:
                            stable = stability.update(detected_static)
                            if stable and cooldown.ready():
                                mapped_action = gesture_map.get(stable, "no_action")
                                result        = _execute(mapped_action, spotify)

                                if _is_error(result):
                                    state             = "error"
                                    message           = result
                                    executing_gesture = stable
                                    action_until      = now + 4.0
                                else:
                                    state             = "executing"
                                    message           = _GESTURE_MESSAGES.get(stable, "Done.")
                                    executing_gesture = stable
                                    action_until      = now + 3.0

                                last_static_fired = detected_static
                                stability.reset()   # require re-hold for next action
                                print(f"[WaveBeat] {stable} -> {result}")

                    else:
                        # Peace alone, one_finger waiting, ok, unrecognised — reset
                        # stability so static holds must start fresh.
                        stability.reset()
                        last_static_fired = None

            # ----------------------------------------------------------------
            # Return from executing / error state
            # ----------------------------------------------------------------
            if state in ("executing", "error") and now > action_until:
                executing_gesture = ""
                if gesture_active:
                    state   = "ready"
                    message = "Gesture controls active."
                else:
                    state   = "standby"
                    message = "Show OK sign to activate gestures."

            # ----------------------------------------------------------------
            # Refresh current Spotify track every 5 seconds
            # ----------------------------------------------------------------
            if now - last_track_time >= 5.0:
                current_track   = spotify.get_current_track() if spotify else ""
                last_track_time = now

            # ----------------------------------------------------------------
            # OK-hold progress for the ring animation
            # ----------------------------------------------------------------
            wake_progress = 0.0
            if ok_detector.start_time is not None and not gesture_active:
                wake_progress = min(
                    1.0,
                    (now - ok_detector.start_time) / ok_detector.hold_seconds,
                )

            # ----------------------------------------------------------------
            # Render
            # Pass executing_gesture during executing/error so the centre orb
            # shows the correct label for the full window (motion gestures are
            # one-frame events; executing_gesture persists until action_until).
            # ----------------------------------------------------------------
            display_gesture = (
                executing_gesture
                if (state in ("executing", "error") and executing_gesture)
                else current_gesture
            )

            track_display = volume_display if now < volume_display_until else current_track
            display.draw(
                frame,
                state,
                message,
                gesture=display_gesture,
                track=track_display,
                camera_on=display.show_camera,
                wake_progress=wake_progress,
            )

            # ----------------------------------------------------------------
            # Keyboard input
            # ----------------------------------------------------------------
            command = display.poll()

            if command == "quit":
                break

            if command == "toggle_body":
                display.show_camera = not display.show_camera
                print(
                    f"[WaveBeat] Camera background "
                    f"{'ON' if display.show_camera else 'OFF'}"
                )

    finally:
        camera.release()
        tracker.close()
        display.close()
        print("[WaveBeat] Closed.")


if __name__ == "__main__":
    main()
