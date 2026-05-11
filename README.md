# WaveBeat - Gesture-Controlled Spotify Controller

WaveBeat is a Raspberry Pi project that allows a user to control Spotify playback using hand gestures. The project uses a Raspberry Pi camera to detect the user's hand, recognises static and movement-based gestures, and sends the matching command to Spotify. It also includes a hologram-style visual interface that shows the current state, detected gesture, action feedback and current track information.

## Student / Project Details

| Field         | Details                                        |
| ------------- | ---------------------------------------------- |
| Project Title | WaveBeat: Gesture-Controlled Spotify Controller |
| Supervisor    | Muhammad Azeem                                  |

## Team Members

| Student Name             | Student Number |
| ------------------------ | -------------- |
| Aline Andrade Costa      | 3144929        |
| Karen Ferreira Magalhaes | 3146094        |
| Sergio Alves da Silva    | 3139115        |

## Project Aim

The aim of this project is to create a touch-free music controller using computer vision and gesture recognition. Instead of using a phone, keyboard or mouse, the user can control Spotify with simple hand gestures in front of the camera.

## Main Features

- Raspberry Pi camera capture using `rpicam-vid` MJPEG streaming.
- Hand tracking using computer vision.
- Static gesture recognition for play, pause, activation and system control.
- Movement gesture recognition for next track, previous track and volume control.
- Spotify playback control using the Spotify Web API through Spotipy.
- Hologram-style Pygame interface for user feedback.
- Cooldowns, hold timers and gesture stability checks to reduce accidental actions.
- Automatic lock after inactivity.

## Gesture Controls

| Gesture                | Action                    |
| ---------------------- | ------------------------- |
| OK sign held           | Activate gesture controls |
| Open palm              | Play                      |
| Fist                   | Pause                     |
| One finger swipe right | Next track                |
| One finger swipe left  | Previous track            |
| Peace move up          | Volume up                 |
| Peace move down        | Volume down               |
| Rock gesture held      | Toggle camera background  |

## Hardware Used

- Raspberry Pi 4
- Raspberry Pi Camera Module 3
- HDMI LCD screen
- Spotify playback device, such as phone, laptop, TV or speaker

## Software / Libraries Used

- Python
- OpenCV
- MediaPipe
- Spotipy
- Pygame
- Raspberry Pi camera tools: `rpicam-vid` / `libcamera-vid`

## Project Structure

```text
project-root/
│
├── main.py
├── config/
│   └── gestures.json
│
├── camera/
│   └── capture.py
│
├── spotify/
│   ├── auth.py
│   └── controller.py
│
├── ui/
│   └── hologram_display.py
│
├── utils/
│   ├── cooldown.py
│   ├── gesture_stability.py
│   └── hold_detector.py
│
└── vision/
    ├── gesture_classifier.py
    ├── hand_tracker.py
    └── motion_gesture_detector.py
```

## Installation

Clone the repository:

```bash
git clone <repository-url>
cd <repository-folder>
```

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install the required Python packages:

```bash
pip install -r requirements.txt
```

Install Raspberry Pi camera tools if needed:

```bash
sudo apt update
sudo apt install -y rpicam-apps
```

## Spotify Setup

Create a Spotify Developer application and add the redirect URI used by the project. Then create a `.env` file in the project root:

```env
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

Do not upload `.env` or `.spotify_cache` to GitHub.

Recommended `.gitignore` entries:

```text
.env
.spotify_cache
__pycache__/
*.pyc
venv/
.venv/
```

## How to Run

Make sure Spotify is open on an active device, then run:

```bash
python main.py
```

Controls inside the interface:

```text
Q = quit
H = toggle camera background
G = gesture guide
```

## How It Works

1. The Raspberry Pi camera sends frames to the program.
2. OpenCV processes the frame and prepares it for hand detection.
3. MediaPipe detects hand landmarks.
4. The gesture classifier checks the hand shape.
5. The motion detector checks movement when needed.
6. The program maps the gesture to a Spotify command.
7. The Spotify controller sends the action to the active Spotify device.
8. The hologram interface shows feedback to the user.

## Testing Summary

| Test Area    | What Was Checked                                   | Result |
| ------------ | -------------------------------------------------- | ------ |
| Camera       | Camera opens, displays correctly and closes safely | Passed |
| Activation   | OK sign must be held before commands work          | Passed |
| Play / Pause | Open palm and fist trigger the correct actions     | Passed |
| Swipes       | One finger swipe changes track                     | Passed |
| Volume       | Peace movement changes volume                      | Passed |
| Cooldown     | Repeated accidental actions are reduced            | Passed |
| Interface    | Gesture state and messages are visible             | Passed |

## Improvements Made After Testing

- Enabled autofocus support for Camera Module 3.
- Added a maximum MJPEG buffer size to avoid memory growth if the stream breaks.
- Kept the newest complete frame to reduce visible delay.
- Added hold detection for the OK activation gesture.
- Added stability checks before static Spotify actions.
- Added cooldowns to avoid actions firing repeatedly.
- Changed volume gestures to peace movement to reduce confusion with pause.

## Known Limitations

- Gesture detection can be affected by poor lighting.
- Fast hand movement may not always be recognised correctly.
- Spotify must have an active playback device available.
- Some Spotify actions may fail if the account/device does not support playback control.
- Camera orientation may need adjustment depending on the screen setup.

## Future Work

- Add user calibration for different hand sizes and camera positions.
- Add a setup script to simplify installation on a new Raspberry Pi.
- Improve recognition in low-light environments.
- Save testing logs automatically for evaluation evidence.
- Add more visual feedback and accessibility options.

## Final Demo Flow

1. Start Spotify on an active device.
2. Run `python main.py`.
3. Show standby mode.
4. Hold the OK sign to activate controls.
5. Use open palm to play.
6. Use fist to pause.
7. Swipe right for next track.
8. Swipe left for previous track.
9. Move peace gesture up/down for volume.
10. Hold rock gesture to toggle the camera background.

## References

Google AI Edge (2026) _MediaPipe Hand Landmarker_. Available at: https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker (Accessed: 11 May 2026).

OpenCV (2026) _OpenCV Documentation_. Available at: https://docs.opencv.org/ (Accessed: 11 May 2026).

Pygame (2026) _Pygame documentation_. Available at: https://www.pygame.org/docs/ (Accessed: 11 May 2026).

Raspberry Pi Ltd. (2026) _Camera software_. Available at: https://www.raspberrypi.com/documentation/computers/camera_software.html (Accessed: 11 May 2026).

Spotify (2026) _Spotify Web API Documentation_. Available at: https://developer.spotify.com/documentation/web-api (Accessed: 11 May 2026).

Spotipy (2026) _Spotipy Documentation_. Available at: https://spotipy.readthedocs.io/ (Accessed: 11 May 2026).
