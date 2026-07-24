# 🏃‍♂️ Subway Runners (Motion-Controlled) - Work in Progress

An interactive endless runner where **your real-world movement controls the game**. 

Instead of using a keyboard or controller, this project uses a webcam and computer vision to track your physical body. When you run, dodge, or jump in front of your camera, the character in the game mimics your movements in real-time!

## 🎮 How It Works
This project bridges Python-based pose estimation with the Game itself:
* **The Tracker (`tracker.py`):** A Python script that uses computer vision (via webcam) to detect player movement, body position, and gestures.
* **The Game:** Built in Python with Ursina and Panda3d libraries , which receives the motion data from the tracker and translates it into character actions (running, switching lanes, jumping).

## 🛠️ Tech Stack
* **Game Engine:** Ursina / Panda3d
* **Computer Vision:** Python (OpenCV / MediaPipe)
* **Integration:** UDP port communication

## 🚧 Current Progress
* [x] Basic Python webcam tracker implementation (`tracker.py`).
* [x] Foundation for the game environment.
* [x] Establish smooth data bridging between tracker and game.
* [ ] Use real game models and sound effects for better experience .
* [ ] Fully polishing.

*Note: Gameplay footage and a demonstration of the webcam tracking in action will be added once it is fully polished!*
