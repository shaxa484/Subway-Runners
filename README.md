# Subway Runners

A first-person, body-controlled endless runner — think *Subway Surfers*, but you're the controller. Lean, jump, and duck with your own body in front of a webcam; no keyboard needed (though it's there as a backup).

> **Status: Alpha.** Core gameplay loop, body tracking, and a packaged Mac build all work. Expect rough edges and a bit rigid tracking.

## How it works

A [MediaPipe](https://developers.google.com/mediapipe) pose-tracking process reads your webcam feed and turns your movement into simple signals — lean left/right, jump, duck, raise a hand — sent locally over UDP. The game itself is a first-person 3D runner built with [Ursina](https://www.ursinaengine.org/) (on top of Panda3D), reading those signals to control your character in real time.

## Controls

| Action | Body | Keyboard (fallback) |
|---|---|---|
| Change lane | Move to left / right | `A` / `D` or arrow keys |
| Jump | Jump in place | `Space` |
| Duck | Crouch (hold) | `S` or down arrow |
| Ready up / Restart | Raise a hand | `Space` |

## Getting started

### Option 1 — Download the release (Mac only, for now)

Grab the latest `.zip` from the [Releases](../../releases) page, unzip it, and:

1. **Right-click → Open** the app the first time (it's unsigned, so macOS will otherwise refuse to launch it — this is normal, one-time).
2. Allow camera access when prompted.
3. Step back so your whole upper body is in frame, then raise a hand or press `Space` to begin.

> **First launch is slow — this is normal, not a hang.** macOS scans a fresh
> unsigned app on first open (Gatekeeper) and this build bundles a fair
> amount of native code (MediaPipe, Panda3D, OpenCV), so the first launch
> can take **30–60+ seconds** before a window appears. **Don't quit and
> reopen it during this time** — repeated attempts while it's still loading
> is the most common cause of it appearing to fail. Give it a full minute
> before assuming something's wrong.
>
> If it still won't open, or macOS blocks it outright, run this once in
> Terminal (adjust the path if you unzipped it somewhere other than
> Downloads):
> ```
> xattr -r -c ~/Downloads/SubwayRunners.app
> ```
> This clears the "downloaded from the internet" quarantine flag that
> otherwise makes macOS refuse to run unsigned apps. You only need to do
> this once per download.

Built and tested on Apple Silicon (M1). If you're on an Intel Mac or Windows — you'll currently need to run from source instead.

### Option 2 — Run from source

```bash
git clone <your-repo-url>
cd Subway-Runners
python3 -m venv venv
source venv/bin/activate
pip install opencv-python mediapipe ursina
```

You'll also need a `pose_landmarker.task` model file (from MediaPipe) in the project root, plus the `models/` and `sounds/` asset folders included in this repo.

Run the main script — tracker and game will be opened by it:
```bash
python3 main.py
```

## Known issues (alpha)

- **Mac-only build for now.** No Windows/Intel Mac build yet — PyInstaller builds are tied to the machine that builds them, so a native build on each platform is needed eventually.
- **Unsigned app.** Expect Gatekeeper's "unidentified developer" warning on first launch.
- **Lighting/track polish is ongoing.** Some visuals are being added and getting improved along the new releases.
- **Calibration is sensitive to camera position/lighting.** Best results standing a few feet back, well-lit, facing the camera directly.

## Roadmap

- Windows build
- More obstacle/track variety
- Persistent high scores
- General visual polish pass

## Built with

- [Ursina Engine](https://www.ursinaengine.org/) / [Panda3D](https://www.panda3d.org/)
- [MediaPipe](https://developers.google.com/mediapipe) Pose Landmarker
- [OpenCV](https://opencv.org/)
- [PyInstaller](https://pyinstaller.org/) for packaging
