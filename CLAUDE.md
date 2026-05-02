I am working on a Raspberry Pi Spotify gesture-control project using Python, OpenCV, MediaPipe, Spotipy, and a Raspberry Pi Camera Module.

Current project idea:
A gesture-controlled Spotify virtual assistant using Raspberry Pi, camera vision, and a hologram-style interface.

I want to improve the project by adding a virtual assistant called “Sendo”. Sendo should behave like a visual assistant similar to Alexa, but using gestures instead of voice.

Important goal:
The app should avoid accidentally detecting normal hand movements as Spotify commands. Spotify gestures should only work after a wake gesture.

Current project structure:

GP-RASPBERRY-PI-PROJECT/
├── camera/
├── config/
│ └── gestures.json
├── docs/
├── spotify/
│ ├── auth.py
│ └── controller.py
├── ui/
│ └── overlay.py
├── utils/
│ ├── cooldown.py
│ ├── gesture_stability.py
│ ├── hold_detector.py
│ └── logger.py
├── vision/
│ ├── gesture_classifier.py
│ ├── hand_tracker.py
│ └── pose_visualizer.py
├── main.py
├── requirements.txt
└── README.md

Current Spotify gesture map in config/gestures.json:

{
"open_palm": "play",
"fist": "pause",
"three_fingers": "next_track",
"peace": "previous_track",
"thumbs_up": "volume_up",
"thumbs_down": "volume_down"
}

Do not add "wake" to gestures.json because wake is not a Spotify action. It is only a system activation gesture.

The gesture classifier already returns:
"wake"

when the user shows only the index finger up.

The utils/hold_detector.py file already exists and should be used to require the wake gesture to be held for 1.5 seconds.

What I want implemented:

1. Add a hologram-style virtual assistant called Sendo.
2. Sendo should appear on the camera screen using OpenCV graphics.
3. Add assistant states:
   - sleeping
   - listening
   - action
   - error

4. Behaviour:
   - App starts with gesture controls OFF.
   - Sendo is sleeping.
   - User holds the wake gesture for 1.5 seconds.
   - Sendo changes to listening mode.
   - Spotify gestures become active.
   - When a Spotify gesture is recognised, Sendo shows the action message.
   - After 10 seconds of inactivity, gesture controls turn OFF again.
   - Sendo goes back to sleeping.

5. Assistant messages:
   - Sleeping: "Hold one finger up to wake me."
   - Wake detected: "I am listening. Show me a Spotify gesture."
   - Open palm/play: "Playing your music."
   - Fist/pause: "Music paused."
   - Three fingers/next: "Skipping to next track."
   - Peace/previous: "Going back one track."
   - Thumbs up: "Increasing volume."
   - Thumbs down: "Decreasing volume."
   - Timeout: "I am sleeping again."
   - Spotify/device error: show the error on screen.

6. Hologram visual ideas:
   - Sleeping = blue/orange calm glowing circle
   - Listening = green glowing circle
   - Action/music = purple animated sound bars
   - Error = red warning style
   - Include animated rings, scan lines, simple robot face, and small status text.

7. Please add a new file:
   ui/virtual_assistant.py

This file should contain a function like:

draw_virtual_assistant(
frame,
state,
message,
gesture="",
action="",
track="",
name="Sendo"
)

It should draw the assistant panel/avatar on the OpenCV frame and return the frame.

8. Update main.py to integrate:
   - HoldDetector("wake", hold_seconds=1.5)
   - gesture_controls_active = False
   - ACTIVE_TIMEOUT = 10.0
   - assistant_state
   - assistant_message
   - draw_virtual_assistant(...)
   - keep the existing hologram/body visualizer mode working
   - keep Q to quit
   - keep H to toggle hologram/body visualizer

9. Do not break existing files:
   - spotify/controller.py
   - spotify/auth.py
   - camera/capture.py
   - vision/hand_tracker.py
   - vision/pose_visualizer.py
   - ui/overlay.py

10. Please give me:

- the full code for ui/virtual_assistant.py
- the full updated main.py
- a short explanation of what changed
- the git commit message

Important:
Make the implementation practical for Raspberry Pi, so avoid heavy graphics or expensive processing. Use only OpenCV, time, math, and numpy if needed.
