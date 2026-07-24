"""
Body-Controlled Endless Runner
--------------------------------
First-person Subway-Surfers-style runner. Controlled by tracker.py, which
sends single-character states over UDP (127.0.0.1:4242):
    C = center / stand up      L = lean left      R = lean right
    J = jump (one-shot)        D = duck (hold)

Also fully playable with a keyboard for testing without the webcam:
    A / Left  = lean left        D / Right = lean right
    Space     = jump             S / Down  = duck (hold)
    R         = restart after game over     Esc = quit

Run this AFTER (or alongside) tracker.py. They talk over localhost UDP,
no other setup needed.
"""

from ursina import *
from panda3d.core import loadPrcFileData
# Every log from this Mac shows "iCCP: known incorrect sRGB profile", and the
# visible symptom (muted/mid-brightness colors washing toward white, while
# highly saturated colors like the obstacles survive) matches a gamma/sRGB
# double-correction issue, not a shader problem. Disabling automatic sRGB
# framebuffer conversion stops Panda3D from re-applying a gamma curve on
# top of whatever macOS's color pipeline is already doing.
loadPrcFileData('', 'framebuffer-srgb false')
import pkgutil
import importlib
import re

# --- macOS shader compatibility fix -----------------------------------
# Diagnostic confirmed this Mac's OpenGL context is legacy 2.1 / GLSL 1.20
# only (Apple's Metal-backed GL translation layer), while Ursina's bundled
# shaders are written for GLSL 1.30/1.40. Unlike newer GLSL, 1.20 doesn't
# have 'in'/'out' qualifiers or custom fragment outputs -- it needs
# 'attribute'/'varying' and writes to the built-in gl_FragColor instead.
# This rewrites every bundled shader's source into 1.20-compatible syntax
# before Ursina/Panda3D ever compiles them.
def _convert_vertex_to_glsl120(src):
    src = re.sub(r'#version\s+1[3-9]0', '#version 120', src)
    src = re.sub(r'^(\s*)in(\s+(?:vec\d|float|int|mat\d|sampler\w*)\s+\w+\s*;)',
                  r'\1attribute\2', src, flags=re.MULTILINE)
    src = re.sub(r'^(\s*)out(\s+(?:vec\d|float|int|mat\d)\s+\w+\s*;)',
                  r'\1varying\2', src, flags=re.MULTILINE)
    return src

def _convert_fragment_to_glsl120(src):
    src = re.sub(r'#version\s+1[3-9]0', '#version 120', src)
    out_match = re.search(r'^[ \t]*out\s+vec4\s+(\w+)\s*;[ \t]*\n?', src, flags=re.MULTILINE)
    if out_match:
        out_name = out_match.group(1)
        src = src[:out_match.start()] + src[out_match.end():]
        src = re.sub(r'\b' + re.escape(out_name) + r'\b', 'gl_FragColor', src)
    src = re.sub(r'^(\s*)in(\s+(?:vec\d|float|int|mat\d|sampler\w*)\s+\w+\s*;)',
                  r'\1varying\2', src, flags=re.MULTILINE)
    src = re.sub(r'\btexture\(', 'texture2D(', src)
    return src

def _patch_shaders_for_mac_gl_compat():
    from ursina.shader import Shader
    import ursina.shaders as shaders_pkg
    patched = []
    for modinfo in pkgutil.iter_modules(shaders_pkg.__path__):
        try:
            mod = importlib.import_module(f'ursina.shaders.{modinfo.name}')
        except Exception as e:
            print(f"[shader patch] could not import {modinfo.name}: {e}")
            continue
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name, None)
            if isinstance(obj, Shader):
                try:
                    if obj.vertex:
                        obj.vertex = _convert_vertex_to_glsl120(obj.vertex)
                    if obj.fragment:
                        obj.fragment = _convert_fragment_to_glsl120(obj.fragment)
                    # Shader.compile() is lazy -- it only rebuilds the actual
                    # compiled native shader if .compiled is still False. If
                    # anything (including Ursina's own internal startup
                    # entities) used this shader before we got here, it's
                    # already compiled from the OLD broken source, and our
                    # string patch above would silently do nothing. Forcing
                    # a fresh compile right now, from the patched source,
                    # fixes that for every entity created from this point on.
                    obj.compile()
                    patched.append(f"{modinfo.name}.{attr_name}")
                except Exception as e:
                    print(f"[shader patch] failed to convert {modinfo.name}.{attr_name}: {e}")
    return patched

_patched_list = _patch_shaders_for_mac_gl_compat()
print(f"[shader patch] recompiled {len(_patched_list)} shader(s) for macOS GL compatibility")
# ------------------------------------------------------------------------

import socket
import random

app = Ursina(title="Body Runner", borderless=False)

# Ursina's built-in Sky() actually uses a real bundled gradient texture
# ('sky_default') and just tints it -- if that texture doesn't load right,
# the tint can't fix it. Building our own plain solid-color dome sidesteps
# that entirely: no texture, just a big sphere in a flat color, always
# rendered behind everything else.
sky_dome = Entity(model='sphere', color=color.rgb32(135, 206, 250), scale=880,
                   double_sided=True, unlit=True, collider=None)
sky_dome.parent = camera
window.color = color.rgb32(135, 206, 250)  # backup in case the dome doesn't cover a gap
application.development_mode = False  # hides the debug/stats overlay

# ---------------------------------------------------------------------------
# UDP listener (non-blocking) -- matches tracker.py exactly, no changes needed
# ---------------------------------------------------------------------------
UDP_IP = "127.0.0.1"
UDP_PORT = 4242
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setblocking(False)
try:
    sock.bind((UDP_IP, UDP_PORT))
    print(f"Listening for tracker on {UDP_IP}:{UDP_PORT}")
except OSError as e:
    print(f"Could not bind UDP socket ({e}) -- keyboard controls still work.")

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------
LANES = {-1: -2.6, 0: 0, 1: 2.6}      # lane index -> world x position
LANE_SNAP_SPEED = 14                   # how quickly player slides between lanes
BASE_SPEED = 14                        # forward units/sec
MAX_SPEED = 34
SPEED_RAMP = 0.15                      # speed gained per second survived
JUMP_FORCE = 8.5
GRAVITY = 22
CAMERA_EYE_HEIGHT = 0.35
CAMERA_DUCK_HEIGHT = -0.15
CAMERA_DUCK_LERP_SPEED = 10
CHUNK_LENGTH = 20
NUM_CHUNKS = 7                         # visible chunks ahead of player at once
COLLISION_WINDOW = 1.1                 # how close (in z) counts as "reached" an obstacle
MIN_DUCK_DURATION = 0.6  # seconds the duck stays active, even if the signal is brief
duck_timer = 0

# ---------------------------------------------------------------------------
# Ground safety net -- one big plane that always exists and always stays
# centered under the player, independent of chunk recycling. The colored
# lane strips (built per-chunk below) sit slightly above this and give the
# lane markings; this plane guarantees there is never a gap of bare white
# under your feet no matter what the chunk logic is doing.
# ---------------------------------------------------------------------------
ground_safety_plane = Entity(model='cube', color=color.rgb32(70, 150, 80),
                              scale=(40, 0.1, 400), position=(0, -0.1, 0),
                              collider=None)

# ---------------------------------------------------------------------------
# Player (invisible capsule-ish box; camera is first-person, attached to it)
# ---------------------------------------------------------------------------
player = Entity(model='cube', visible=False, collider=None,
                 position=(0, 1, 0), scale=(1.2, 1.8, 1.2))
camera.parent = player
camera.position = (0, 0.35, 0)   # eye height relative to player's own origin
camera.rotation = (0, 0, 0)
camera.fov = 90

lane = 0                # current lane index: -1, 0, 1
target_x = LANES[lane]
is_jumping = False
is_ducking = False
y_velocity = 0
ground_y = 1.0
distance_traveled = 0
coins_collected = 0
speed = BASE_SPEED
game_over = False
run_time = 0

coin_sound = Audio('coin', autoplay=False)
game_over_sound = Audio('death', autoplay=False)



# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
# Fixed x positions like -0.85 assume a specific aspect ratio and can clip
# off-screen on narrower windows. Anchoring relative to window.aspect_ratio
# keeps this text fully on-screen no matter the window's shape.
UI_LEFT = -window.aspect_ratio / 2 + 0.05

score_text = Text(text="Score: 0", position=(UI_LEFT, 0.45), scale=1.6, color=color.white,
                   background=True)
coin_text = Text(text="Coins: 0", position=(UI_LEFT, 0.40), scale=1.4, color=color.yellow,
                  background=True)
help_text = Text(
    text="Lean L/R = change lane   Jump = hop   Duck = crouch\n(Keyboard: A/D, Space, S)",
    position=(UI_LEFT, -0.38), scale=0.9, color=color.rgba(255, 255, 255, 200),
    background=True
)
game_over_text = Text(text="", position=(0, 0.1), origin=(0, 0), scale=2.5, color=color.red,
                       enabled=False, background=True)
restart_text = Text(text="Press R to restart", position=(0, -0.02), origin=(0, 0), scale=1.4,
                     color=color.white, enabled=False, background=True)


# ---------------------------------------------------------------------------
# Chunk: one 20-unit slice of track. Holds ground, buildings, obstacles, coins.
# Recycled (moved to the front) once the player passes it.
# ---------------------------------------------------------------------------
class Chunk:
    def __init__(self, z_start):
        self.z_start = z_start
        self.entities = []
        self.obstacles = []   # list of dicts: {entity, lane, world_z, type, resolved}
        self.coins = []
        self.build(z_start)

    def clear(self):
        for e in self.entities:
            destroy(e)
        self.entities.clear()
        self.obstacles.clear()
        self.coins.clear()

    def build(self, z_start):
        self.z_start = z_start
        mid_z = z_start + CHUNK_LENGTH / 2

        # Ground: three lane strips, subtle color difference so lanes read clearly
        for lx, c in zip((-2.6, 0, 2.6), (color.rgb32(70, 70, 78), color.rgb32(85, 85, 95), color.rgb32(70, 70, 78))):
            ground = Entity(model='cube', color=c, position=(lx, 0, mid_z),
                             scale=(2.4, 0.2, CHUNK_LENGTH))
            self.entities.append(ground)

        # City buildings on both sides
        for side in (-1, 1):
            num_buildings = random.randint(2, 4)
            for i in range(num_buildings):
                h = random.uniform(4, 14)
                bz = z_start + random.uniform(0, CHUNK_LENGTH)
                bx = side * random.uniform(6, 11)
                b = Entity(model='cube',
                           color=color.rgb32(*[random.randint(90, 160)] * 3),
                           position=(bx, h / 2, bz),
                           scale=(random.uniform(3, 6), h, random.uniform(3, 6)))
                self.entities.append(b)

        # Obstacle (roughly 70% chance per chunk, one lane blocked)
        if random.random() < 0.7:
            obs_lane = random.choice([-1, 0, 1])
            obs_type = random.choice(['barrier', 'beam', 'train'])
            oz = mid_z + random.uniform(-3, 3)
            ox = LANES[obs_lane]

            if obs_type == 'barrier':      # low box -- jump over it
                e = Entity(model='short_obstacle', position=(ox, 0.9, oz), scale=(0.5,0.5,0.5),rotation_y=90)
                
            elif obs_type == 'beam':        # overhead bar -- duck under it
                e = Entity(model='high_obstacle', position=(ox, 1.7, oz), scale=(0.5,0.5,0.5),rotation_y=90)
            else:                            # 'train' -- full lane, must switch
                e = Entity(model='train', position=(ox, 0.8, oz), scale=(0.4, 0.4, 0.4),rotation_y=90)

            self.entities.append(e)
            self.obstacles.append({'entity': e, 'lane': obs_lane, 'z': oz,
                                    'type': obs_type, 'resolved': False})

        # Coins -- a little arc of 5 in a free lane
        free_lanes = [-1, 0, 1]
        if self.obstacles:
            free_lanes.remove(self.obstacles[0]['lane'])
        coin_lane = random.choice(free_lanes)
        coin_z_start = z_start + random.uniform(2, 6)
        for i in range(5):
            cz = coin_z_start + i * 1.4
            coin = Entity(model='coin', 
                          position=(LANES[coin_lane], 1.1, cz), scale=1.4)
            self.entities.append(coin)
            self.coins.append({'entity': coin, 'lane': coin_lane, 'z': cz, 'collected': False})


chunks = [Chunk(i * CHUNK_LENGTH) for i in range(NUM_CHUNKS)]


def reset_game():
    global lane, target_x, is_jumping, is_ducking, y_velocity
    global distance_traveled, coins_collected, speed, game_over, run_time, chunks

    lane = 0
    target_x = LANES[lane]
    is_jumping = False
    is_ducking = False
    y_velocity = 0
    player.position = (0, ground_y, 0)
    distance_traveled = 0
    coins_collected = 0
    speed = BASE_SPEED
    game_over = False
    run_time = 0

    for c in chunks:
        c.clear()
    chunks = [Chunk(i * CHUNK_LENGTH) for i in range(NUM_CHUNKS)]

    game_over_text.enabled = False
    restart_text.enabled = False


def end_game(reason):
    global game_over
    game_over = True
    game_over_text.text = f"GAME OVER\n{reason}"
    game_over_text.enabled = True
    restart_text.enabled = True
    game_over_sound.play()


# ---------------------------------------------------------------------------
# Input: keyboard (fallback / testing) + UDP (tracker)
# ---------------------------------------------------------------------------
def input(key):
    global lane, target_x, is_jumping, y_velocity, is_ducking

    if key == 'r' and game_over:
        reset_game()
        return

    if game_over:
        return

    if key in ('a', 'left arrow'):
        lane = max(-1, lane - 1)
        target_x = LANES[lane]
        is_ducking = False
    elif key in ('d', 'right arrow'):
        lane = min(1, lane + 1)
        target_x = LANES[lane]
        is_ducking = False
    elif key == 'space' and not is_jumping and not is_ducking:
        is_jumping = True
        y_velocity = JUMP_FORCE
    elif key in ('s', 'down arrow'):
        is_ducking = True
    elif key in ('s up', 'down arrow up'):
        is_ducking = False


def read_tracker():
    """Non-blocking UDP read. Returns the latest state char or None."""
    latest = None
    try:
        while True:
            data, _ = sock.recvfrom(64)
            latest = data.decode('utf-8').strip()
    except BlockingIOError:
        pass
    except OSError:
        pass
    return latest


def apply_tracker_state(state):
    global lane, target_x, is_jumping, y_velocity, is_ducking

    if game_over:
        return

    if state == 'L':
        lane = -1
        target_x = LANES[lane]
        is_ducking = False
    elif state == 'R':
        lane = 1
        target_x = LANES[lane]
        is_ducking = False
    elif state == 'C':
        lane = 0
        target_x = LANES[lane]
        is_ducking = False
    elif state == 'J':
        if not is_jumping and not is_ducking:
            is_jumping = True
            y_velocity = JUMP_FORCE
    elif state == 'D':
        is_ducking = True


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def update():
    global is_jumping, y_velocity, distance_traveled, speed, run_time, coins_collected

    state = read_tracker()
    if state:
        apply_tracker_state(state)
    global duck_timer
    duck_timer = MIN_DUCK_DURATION if is_ducking else max(duck_timer - time.dt, 0)
    effective_ducking = is_ducking or duck_timer > 0

    if game_over:
        return

    run_time += time.dt
    speed = min(MAX_SPEED, BASE_SPEED + run_time * SPEED_RAMP)

    # Forward movement
    player.z += speed * time.dt
    distance_traveled += speed * time.dt
    ground_safety_plane.z = player.z  # keep the safety-net ground under the player

    # Smooth lane snapping
    player.x = lerp(player.x, target_x, time.dt * LANE_SNAP_SPEED)

    # Jump physics
    if is_jumping:
        player.y += y_velocity * time.dt
        y_velocity -= GRAVITY * time.dt
        if player.y <= ground_y:
            player.y = ground_y
            is_jumping = False
            y_velocity = 0

    # Camera bob for a bit of "running" feel
    target_cam_y = CAMERA_DUCK_HEIGHT if effective_ducking else CAMERA_EYE_HEIGHT
    bob = abs(math.sin(run_time * 9)) * 0.03 if not (is_jumping or effective_ducking) else 0
    camera.y = lerp(camera.y, target_cam_y + bob, time.dt * CAMERA_DUCK_LERP_SPEED)

    # Recycle chunks that are now behind the player
    for c in chunks:
        if c.z_start + CHUNK_LENGTH < player.z - 6:
            farthest_z = max(ch.z_start for ch in chunks)
            c.clear()
            c.build(farthest_z + CHUNK_LENGTH)

    # Coin collection
    for c in chunks:
        for coin in c.coins:
            if coin['collected']:
                continue
            if coin['lane'] == lane and abs(coin['z'] - player.z) < 0.9:
                coin['collected'] = True
                coin['entity'].enabled = False
                coins_collected += 1
                coin_sound.play()

    # Obstacle collision
    for c in chunks:
        for obs in c.obstacles:
            if obs['resolved']:
                continue
            if abs(obs['z'] - player.z) < COLLISION_WINDOW and obs['lane'] == lane:
                obs['resolved'] = True
                if obs['type'] == 'barrier' and is_jumping:
                    continue
                elif obs['type'] == 'beam' and effective_ducking:
                    continue
                else:
                    end_game({
                        'barrier': "Hit a barrier -- try jumping!",
                        'beam': "Hit a beam -- try ducking!",
                        'train': "Ran into a train -- switch lanes!",
                    }[obs['type']])

    score_text.text = f"Score: {int(distance_traveled) + coins_collected * 10}"
    coin_text.text = f"Coins: {coins_collected}"


import os
if os.environ.get('AUTO_SCREENSHOT'):
    def _snap():
        base.win.saveScreenshot('verify5.png')
        application.quit()
    invoke(_snap, delay=4)

import os
if os.environ.get('AUTO_SCREENSHOT'):
    def _snap():
        base.win.saveScreenshot('verify6.png')
        application.quit()
    invoke(_snap, delay=4)
bg_music = Audio('main.mp3', loop=True, autoplay=True)
bg_music.volume = 0.5 
app.run()
