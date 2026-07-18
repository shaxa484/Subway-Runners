# 🏃‍♂️ Subway Runners (Motion-Controlled) - Work in Progress

An interactive endless runner where **your real-world movement controls the game**. 

Instead of using a keyboard or controller, this project uses a webcam and computer vision to track your physical body. When you run, dodge, or jump in front of your camera, the character in the game mimics your movements in real-time!

## 🎮 How It Works
This project bridges Python-based pose estimation with the Godot Game Engine:
* **The Tracker (`tracker.py`):** A Python script that uses computer vision (via webcam) to detect player movement, body position, and gestures.
* **The Game:** Built in Godot, which receives the motion data from the Python tracker and translates it into character actions (running, switching lanes, jumping).

## 🛠️ Tech Stack
* **Game Engine:** Godot Engine (GDScript)
* **Computer Vision:** Python (OpenCV / MediaPipe)
* **Integration:** Python to Godot communication

## 🚧 Current Progress
* [x] Basic Python webcam tracker implementation (`tracker.py`).
* [x] Foundation for the Godot game environment.
* [ ] Establish smooth data bridging between Python and Godot.
* [ ] Map real-world body movements to specific in-game controls.
* [ ] Implement obstacles, procedural generation, and scoring.

*Note: Gameplay footage and a demonstration of the webcam tracking in action will be added once the core loop is fully connected!*
