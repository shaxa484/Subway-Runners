"""
Single-app launcher for Body Runner.

Spawns tracker.py's camera/MediaPipe loop as a separate OS process (so it
never competes with the game's rendering for the same thread/GIL), then
runs the game itself in this, the main process. Both processes still just
talk over the same UDP socket as before -- nothing about that changes.

This is the file to point PyInstaller at, not game.py or tracker.py directly.
"""
import multiprocessing
import sys
import os
from pathlib import Path

def _resource_path_setup():
    if getattr(sys, 'frozen', False):
        exe_path = Path(sys.executable).resolve()
        if '.app' in str(exe_path):
            resource_path = exe_path.parent.parent / 'Resources'
        else:
            resource_path = Path(sys._MEIPASS)
        os.environ['SUBWAY_RUNNER_ASSETS'] = str(resource_path)
        os.chdir(resource_path)

def main():
    # Required on Windows/macOS frozen apps that use multiprocessing --
    # without this, the child process re-imports and re-runs this whole
    # file, causing an infinite relaunch loop. Must be the first thing
    # that runs.
    multiprocessing.freeze_support()
    
    _resource_path_setup()

    from trackerv import run_tracker
    tracker_process = multiprocessing.Process(target=run_tracker, daemon=True)
    tracker_process.start()

    try:
        import game  # noqa: F401 -- importing runs game.py's app.run() and blocks here
        globals()['update'] = game.update
        globals()['input'] = game.input
        game.app.run()
    finally:
        tracker_process.terminate()


if __name__ == "__main__":
    main()