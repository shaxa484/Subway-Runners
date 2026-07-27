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


def _resource_path_setup():
    """When frozen by PyInstaller, bundled data (models/, sounds/, the
    MediaPipe .task file) gets unpacked to a temp folder at sys._MEIPASS,
    not to the folder the exe sits in. Point both scripts' asset lookups
    there when running frozen; in normal dev use, this does nothing."""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        os.chdir(base_path)


def main():
    # Required on Windows/macOS frozen apps that use multiprocessing --
    # without this, the child process re-imports and re-runs this whole
    # file, causing an infinite relaunch loop. Must be the first thing
    # that runs.
    multiprocessing.freeze_support()

    _resource_path_setup()

    from tracker import run_tracker
    tracker_process = multiprocessing.Process(target=run_tracker, daemon=True)
    tracker_process.start()

    try:
        import game  # noqa: F401 -- importing runs game.py's app.run() and blocks here
    finally:
        tracker_process.terminate()


if __name__ == "__main__":
    main()