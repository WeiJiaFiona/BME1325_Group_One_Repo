import os
import string
import random
import json
from os import listdir
import os

import datetime
from django.shortcuts import render, redirect, HttpResponseRedirect
from django.http import HttpResponse, JsonResponse
from global_methods import *

from django.contrib.staticfiles.templatetags.staticfiles import static
from .models import *

import time, datetime, uuid
from django.views.decorators.csrf import csrf_exempt
from pathlib import Path

import subprocess
from django.http import JsonResponse
import sys
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from app_core.app.api_v1 import (
    ApiError,
    complete_handoff,
    queue_snapshot,
    reset_user_mode_session,
    request_handoff,
    start_encounter,
    user_mode_chat_turn,
    user_mode_session_status,
)


def _resolve_pointer_path(path: Path) -> Path:
    if path.is_dir():
        return path
    if path.is_file():
        try:
            candidate = Path(path.read_text(encoding="utf-8").strip())
            if candidate.exists():
                return candidate
        except Exception:
            pass
    return path


STORAGE_ROOT = _resolve_pointer_path(FRONTEND_ROOT / "storage")
TEMP_ROOT = _resolve_pointer_path(Path(os.environ.get("EDSIM_TEMP_DIR", str(FRONTEND_ROOT / "temp_storage"))))
fs_temp_storage = str(TEMP_ROOT)


def _storage_path(*parts: str) -> str:
    return str(STORAGE_ROOT.joinpath(*parts))


def _temp_path(*parts: str) -> str:
    return str(TEMP_ROOT.joinpath(*parts))

def _backend_mode() -> str:
    mode = str(os.environ.get("EDSIM_MODE", "auto")).strip().lower()
    return mode if mode in {"auto", "user"} else "auto"


def _current_sim_code(default: Optional[str] = None) -> Optional[str]:
    try:
        with open(_temp_path("curr_sim_code.json"), encoding="utf-8") as f:
            payload = json.load(f)
        return payload.get("sim_code") or default
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _resolve_backend_dir() -> Path:
    env_backend = os.environ.get("EDSIM_BACKEND_DIR", "").strip()
    if env_backend:
        return Path(env_backend)
    candidate = PROJECT_ROOT / "reverie" / "backend_server"
    if candidate.exists():
        return candidate
    return candidate


def _list_running_reverie_processes(backend_dir: Path) -> list[int]:
    backend_dir_str = str(backend_dir.resolve()).lower()
    running = []
    for proc in psutil.process_iter(["pid", "cmdline", "cwd"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            cwd = (proc.info.get("cwd") or "").lower()
            normalized_cmd = " ".join(cmdline).lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

        if "reverie.py" not in normalized_cmd:
            continue
        if backend_dir_str in normalized_cmd or cwd == backend_dir_str:
            running.append(proc.info["pid"])
    return running


def _list_numeric_step_files(directory: str) -> list[int]:
    steps = []
    if not os.path.exists(directory):
        return steps
    for file_path in find_filenames(directory, ".json"):
        name = file_path.split("/")[-1].strip()
        if not name or name.startswith("."):
            continue
        try:
            steps.append(int(name.split(".")[0]))
        except Exception:
            continue
    return sorted(steps)


def _sanitize_environment_snapshot(sim_code: str, environment: dict) -> dict:
    """Keep frontend-reported tile coordinates inside the Tiled map bounds."""
    try:
        with open(_storage_path(sim_code, "reverie", "maze_visuals.json")) as f:
            visuals = json.load(f)
        max_x = max(0, int(visuals.get("width", 0)) - 1)
        max_y = max(0, int(visuals.get("height", 0)) - 1)
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
        max_x = max_y = 0

    sanitized = {}
    for persona_name, position in (environment or {}).items():
        if not isinstance(position, dict):
            continue
        try:
            x = int(round(float(position.get("x", 0))))
            y = int(round(float(position.get("y", 0))))
        except (TypeError, ValueError):
            continue
        clean_position = dict(position)
        clean_position["x"] = min(max(x, 0), max_x)
        clean_position["y"] = min(max(y, 0), max_y)
        sanitized[persona_name] = clean_position
    return sanitized


def _read_curr_step_pointer() -> Optional[int]:
    try:
        with open(_temp_path("curr_step.json")) as f:
            payload = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        return None
    value = payload.get("step")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _read_status_step(sim_code: str) -> Optional[int]:
    try:
        with open(_storage_path(sim_code, "sim_status.json")) as f:
            payload = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, TypeError, OSError):
        return None
    value = payload.get("step")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_runtime_sync(sim_code: str, status_step: Optional[int] = None) -> dict:
    movement_steps = _list_numeric_step_files(_storage_path(sim_code, "movement"))
    environment_steps = _list_numeric_step_files(_storage_path(sim_code, "environment"))
    curr_step_pointer = _read_curr_step_pointer()
    latest_movement_step = movement_steps[-1] if movement_steps else None
    latest_environment_step = environment_steps[-1] if environment_steps else None

    movement_matches_status = (
        status_step is not None and latest_movement_step == status_step
    )
    curr_step_within_expected_window = (
        status_step is not None
        and curr_step_pointer is not None
        and curr_step_pointer in {status_step, status_step + 1}
    )
    environment_within_expected_window = (
        status_step is not None
        and latest_environment_step is not None
        and latest_environment_step in {status_step, status_step + 1}
    )

    runtime_sources = {
        "status_step": status_step,
        "curr_step_pointer": curr_step_pointer,
        "latest_movement_step": latest_movement_step,
        "latest_environment_step": latest_environment_step,
        "movement_matches_status": movement_matches_status,
        "curr_step_within_expected_window": curr_step_within_expected_window,
        "environment_within_expected_window": environment_within_expected_window,
    }
    runtime_sources["in_sync"] = all(
        value for value in (
            movement_matches_status,
            curr_step_within_expected_window,
            environment_within_expected_window,
        )
    )
    runtime_sources["notes"] = [
        "sim_status.json is the dashboard source of truth.",
        "curr_step.json is a runtime pointer and startup handshake signal.",
        "movement/<step>.json drives map execution; environment/<step>.json captures map position snapshots.",
    ]
    return runtime_sources

def landing(request): 
    context = {}
    template = "landing/landing.html"
    return render(request, template, context)

def demo(request, sim_code, step, play_speed="2"): 
    move_file = f"compressed_storage/{sim_code}/master_movement.json"
    meta_file = f"compressed_storage/{sim_code}/meta.json"
    step = int(step)
    play_speed_opt = {"1": 1, "2": 2, "3": 4, "4": 8, "5": 16, "6": 32}
    if play_speed not in play_speed_opt: play_speed = 2
    else: play_speed = play_speed_opt[play_speed]

    # Loading the basic meta information about the simulation
    meta = dict() 
    with open(meta_file) as json_file: 
        meta = json.load(json_file)
    sec_per_step = meta["sec_per_step"]
    start_datetime = datetime.datetime.strptime(meta["curr_time"], 
                                               '%B %d, %Y, %H:%M:%S')
    # for i in range(step): 
    #     start_datetime += datetime.timedelta(seconds=sec_per_step)
    start_datetime = start_datetime.strftime("%Y-%m-%dT%H:%M:%S")

    # Loading the movement file
    raw_all_movement = dict()
    with open(move_file) as json_file: 
        raw_all_movement = json.load(json_file)
    
    # Loading all names of the personas
    persona_names = []
    persona_names_set = set()
    for p in list(raw_all_movement["0"].keys()): 
        persona_names += [{"original": p, 
                           "underscore": p.replace(" ", "_"), 
                           "initial": p[0] + p.split(" ")[-1][0]}]
        persona_names_set.add(p)

    # Use replay's method for persona_init_pos
    persona_init_pos = []
    starting_pos_file =  f"compressed_storage/{sim_code}/starting_pos.json"
    with open(starting_pos_file) as json_file:  
        persona_init_pos_dict = json.load(json_file)
        for key, val in persona_init_pos_dict.items(): 
            if key in persona_names_set: 
                persona_init_pos += [[key, val["x"], val["y"]]]

    # Preparing the initial step and all_movement
    init_prep = dict() 
    for int_key in range(step+1): 
        key = str(int_key)
        val = raw_all_movement[key]
        for p in persona_names_set: 
            if p in val: 
                init_prep[p] = val[p]
    all_movement = dict()
    all_movement[step] = init_prep
    for int_key in range(step+1, len(raw_all_movement.keys())): 
        all_movement[int_key] = raw_all_movement[str(int_key)]

    sprite_files = []
    for i in find_filenames(f"static_dirs/assets/characters/", ".png"): 
        x = i.split("/")[-1].strip()
        if x[0] != ".": 
            sprite_files.append(x.split(".")[0])
            print(x.split(".")[0])

    maze_meta = json.load(open(_storage_path(sim_code, "reverie", "maze_visuals.json")))

    context = {"sim_code": sim_code,
               "step": step,
               "persona_names": persona_names,
               "persona_init_pos": persona_init_pos,  # Now a list
               "all_movement": json.dumps(all_movement), 
               "start_datetime": start_datetime,
               "sec_per_step": sec_per_step,
               "play_speed": play_speed,
               "mode": "demo",
               "sprite_maps": sprite_files,
                "maze_size": [maze_meta["width"], maze_meta["height"]]}
    
    template = "demo/demo.html"
    return render(request, template, context)

def UIST_Demo(request): 
    return demo(request, "March20_the_ville_n25_UIST_RUN-step-1-141", 2160, play_speed="3")

def home(request):
    requested_ui_mode = str(request.GET.get("ui_mode", "auto")).strip().lower()
    if requested_ui_mode not in {"auto", "user"}:
        requested_ui_mode = "auto"
    backend_mode = _backend_mode()
    effective_ui_mode = backend_mode
    mode_switch_message = ""
    if requested_ui_mode != effective_ui_mode:
        mode_switch_message = (
            f"Backend is started with EDSIM_MODE={backend_mode}. "
            f"To use {requested_ui_mode} mode, restart backend with EDSIM_MODE={requested_ui_mode}."
        )

    f_curr_sim_code = _temp_path("curr_sim_code.json")
    f_curr_step = _temp_path("curr_step.json")

    if (not check_if_file_exists(f_curr_sim_code)) or (not check_if_file_exists(f_curr_step)):
        context = {"error": "Backend is not started yet. Please start simulation backend first."}
        template = "home/error_start_backend.html"
        return render(request, template, context)

    with open(f_curr_sim_code) as json_file:  
        sim_code = json.load(json_file).get("sim_code", "")
    
    with open(f_curr_step) as json_file:  
        step = json.load(json_file).get("step", 0)

    if not sim_code:
        context = {"error": "Invalid backend runtime state. Please restart backend."}
        template = "home/error_start_backend.html"
        return render(request, template, context)

    # os.remove(f_curr_step)

    persona_names = []
    persona_names_set = set()
    personas_dir = _storage_path(sim_code, "personas")
    env_dir = _storage_path(sim_code, "environment")
    maze_visuals_path = _storage_path(sim_code, "reverie", "maze_visuals.json")
    if (not os.path.exists(personas_dir)) or (not os.path.exists(env_dir)) or (not os.path.exists(maze_visuals_path)):
        context = {"error": f"Simulation data for `{sim_code}` is not ready yet. Start backend and try again."}
        template = "home/error_start_backend.html"
        return render(request, template, context)

    for i in find_filenames(personas_dir, ""): 
        x = i.split("/")[-1].strip()
        if x[0] != ".": 
            persona_names += [[x, x.replace(" ", "_")]]
            persona_names_set.add(x)

    persona_init_pos = []
    file_count = []
    for i in find_filenames(env_dir, ".json"):
        x = i.split("/")[-1].strip()
        if x[0] != ".": 
            file_count += [int(x.split(".")[0])]
    if not file_count:
        context = {"error": f"No environment snapshots found for `{sim_code}` yet."}
        template = "home/error_start_backend.html"
        return render(request, template, context)
    curr_json = _storage_path(sim_code, "environment", f"{str(max(file_count))}.json")
    with open(curr_json) as json_file:  
        persona_init_pos_dict = json.load(json_file)
        for key, val in persona_init_pos_dict.items(): 
            if key in persona_names_set: 
                persona_init_pos += [[key, val["x"], val["y"]]]
                
    with open(_storage_path(sim_code, "reverie", "maze_visuals.json")) as json_file:  
        maze_meta = json.load(json_file)

    # Guard against stale curr_step values: frontend should start from an
    # existing movement frame, otherwise update loop can wait forever.
    movement_steps = _list_numeric_step_files(_storage_path(sim_code, "movement"))
    if movement_steps and step not in movement_steps:
        step = max(movement_steps)
    elif not movement_steps:
        step = 0

    runtime_sources = _build_runtime_sync(sim_code, status_step=_read_status_step(sim_code))

    context = {
        "sim_code": sim_code,
        "step": step,
        "persona_names": persona_names,
        "persona_init_pos": persona_init_pos,
        "mode": "simulate",
        "ui_mode": requested_ui_mode,
        "effective_ui_mode": effective_ui_mode,
        "backend_mode": backend_mode,
        "mode_switch_message": mode_switch_message,
        "runtime_sources": runtime_sources,
        "maze_size": [maze_meta["width"], maze_meta["height"]],
    }
    template = "home/home.html"
    return render(request, template, context)

def get_maze_visuals(request, sim_code, mode):
    mode = mode
    sim_code = sim_code

    # Source Maze Visual from different places depending on mode
    if(mode == "simulate"):
        curr_json = _storage_path(sim_code, "reverie", "maze_visuals.json")
        with open(curr_json, 'r') as json_file:  
            maze_visuals = json.load(json_file)
    else:
        curr_json = f'compressed_storage/{sim_code}/maze_visuals.json'
        with open(curr_json, 'r') as json_file:  
            maze_visuals = json.load(json_file)

    return JsonResponse(maze_visuals)


def replay(request, sim_code, step): 
    sim_code = sim_code
    step = int(step)

    persona_names = []
    persona_names_set = set()

    meta_file = _storage_path(sim_code, "environment", "0.json")
    with open(meta_file, 'r') as json_file: 
        meta = json.load(json_file)

    for name in meta.keys():
        persona_names += [[name, name.replace(" ", "_")]]
        persona_names_set.add(name)

    persona_init_pos = []
    file_count = []
    for i in find_filenames(_storage_path(sim_code, "environment"), ".json"):
        x = i.split("/")[-1].strip()
        if x[0] != ".": 
            file_count += [int(x.split(".")[0])]
    curr_json = _storage_path(sim_code, "environment", "0.json")
    with open(curr_json) as json_file:  
        persona_init_pos_dict = json.load(json_file)
        for key, val in persona_init_pos_dict.items(): 
            if key in persona_names_set: 
                persona_init_pos += [[key, val["x"], val["y"]]]


    maze_meta = json.load(open(_storage_path(sim_code, "reverie", "maze_visuals.json")))

    context = {
        "sim_code": sim_code,
        "step": step,
        "persona_names": persona_names,
        "persona_init_pos": persona_init_pos,
        "mode": "replay",
        "ui_mode": "auto",
        "effective_ui_mode": "auto",
        "backend_mode": _backend_mode(),
        "mode_switch_message": "",
        "maze_size": [maze_meta["width"], maze_meta["height"]],
    }
    template = "home/home.html"
    return render(request, template, context)

def replay_persona_state(request, sim_code, step, persona_name): 
    sim_code = sim_code
    step = int(step)

    persona_name_underscore = persona_name
    persona_name = persona_name_underscore.replace("_", " ")
    memory = _storage_path(sim_code, "personas", persona_name, "bootstrap_memory")
    if not os.path.exists(memory): 
        memory = f"compressed_storage/{sim_code}/personas/{persona_name}/bootstrap_memory"

    with open(memory + "/scratch.json") as json_file:  
        scratch = json.load(json_file)

    with open(memory + "/spatial_memory.json") as json_file:  
        spatial = json.load(json_file)

    with open(memory + "/associative_memory/nodes.json") as json_file:  
        associative = json.load(json_file)

    a_mem_event = []
    a_mem_chat = []
    a_mem_thought = []

    for count in range(len(associative.keys()), 0, -1): 
        node_id = f"node_{str(count)}"
        node_details = associative[node_id]

        if node_details["type"] == "event":
            a_mem_event += [node_details]

        elif node_details["type"] == "chat":
            a_mem_chat += [node_details]

        elif node_details["type"] == "thought":
            a_mem_thought += [node_details]
    
    # Check if sprite exists, if not grab sprite offset for that persona. Such as Patient_3 to Patient_2 sprite
    if(not os.path.exists(f"static_dirs/assets/characters/{persona_name_underscore}.png")):
        sprite_offset = 0
        persona_tag = persona_name_underscore.split("_")[0]
        for i in find_filenames(f"static_dirs/assets/characters/", ".png"): 
            x = i.split("/")[-1].strip()
            if x[0] != "." and persona_tag in x: 
                sprite_offset += 1

        sprite_offset= int(persona_name_underscore.split("_")[-1]) % sprite_offset
        sprite_map = "Patient_" + str(sprite_offset+1)
    else:
        sprite_map = persona_name_underscore


    context = {"sim_code": sim_code,
               "step": step,
               "persona_name": persona_name, 
               "persona_name_underscore": persona_name_underscore, 
               "scratch": scratch,
               "spatial": spatial,
               "a_mem_event": a_mem_event,
               "a_mem_chat": a_mem_chat,
               "a_mem_thought": a_mem_thought,
               "sprite_map": sprite_map}
    template = "persona_state/persona_state.html"
    return render(request, template, context)

def path_tester(request):
    context = {}
    template = "path_tester/path_tester.html"
    return render(request, template, context)

def process_environment(request): 
    """
    <FRONTEND to BACKEND> 
    This sends the frontend visual world information to the backend server. 
    It does this by writing the current environment representation to 
    "storage/environment.json" file. 

    ARGS:
        request: Django request
    RETURNS: 
        HttpResponse: string confirmation message. 
    """
    data = json.loads(request.body)
    step = data["step"]
    sim_code = data["sim_code"]
    environment = _sanitize_environment_snapshot(sim_code, data["environment"])

    with open(_storage_path(sim_code, "environment", f"{step}.json"), "w") as outfile:
        outfile.write(json.dumps(environment, indent=2))
        outfile.flush()

    return HttpResponse("received")

def update_environment(request): 
    """
    <BACKEND to FRONTEND> 
    This sends the backend computation of the persona behavior to the frontend
    visual server. 
    It does this by reading the new movement information from 
    "storage/movement.json" file.

    ARGS:
        request: Django request
    RETURNS: 
        HttpResponse
    """
    data = json.loads(request.body)
    step = data["step"]
    sim_code = data["sim_code"]

    response_data = {"<step>": -1}
    if (check_if_file_exists(_storage_path(sim_code, "movement", f"{step}.json"))):
        with open(_storage_path(sim_code, "movement", f"{step}.json")) as json_file: 
            response_data = json.load(json_file)
            response_data["<step>"] = step

    return JsonResponse(response_data)

def path_tester_update(request): 
    """
    Processing the path and saving it to path_tester_env.json temp storage for 
    conducting the path tester. 

    ARGS:
        request: Django request
    RETURNS: 
        HttpResponse: string confirmation message.
    """
    data = json.loads(request.body)
    camera = data["camera"]

    with open(_temp_path("path_tester_env.json"), "w") as outfile:
        outfile.write(json.dumps(camera, indent=2))

    return HttpResponse("received")

from django.http import FileResponse
def get_image_png(request):
    image_url = request.GET.get("url")  # retrieve from query param

    # Construct the absolute path to your image file
    # Replace 'my_image.png' with the actual filename and path
    image_path = os.path.join('static_dirs', image_url)

    try:
        # Open the file in binary read mode
        # 'as_attachment=True' will force a download, False will display in browser
        return FileResponse(open(image_path, 'rb'), content_type='image/png', as_attachment=False)
    except FileNotFoundError:
        from django.http import HttpResponseNotFound
        return HttpResponseNotFound("Image not found.")

@csrf_exempt
def send_sim_command(request):
    """
    Frontend -> backend control: write a command file into temp storage.
    Body: {"command": "run 10"}
    Returns: {"ok": True, "id": "<id>"}
    """
    try:
        payload = json.loads(request.body)
        cmd = payload.get("command")
        if not cmd:
            return JsonResponse({"ok": False, "error": "no command provided"}, status=400)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    cmd_dir = Path(_temp_path("commands"))
    cmd_dir.mkdir(parents=True, exist_ok=True)

    cmd_id = str(int(time.time() * 1000))
    file_path = cmd_dir / f"cmd_{cmd_id}.json"
    with open(file_path, "w") as f:
        json.dump({"id": cmd_id, "command": cmd, "created_at": datetime.datetime.utcnow().isoformat()}, f)

    return JsonResponse({"ok": True, "id": cmd_id})


def get_sim_output(request):
    """
    Return all outputs recorded by the server. The frontend can poll and
    append new lines to a terminal UI.
    Optional query param: since_id to only get outputs after a given id.
    """
    out_file = Path(_temp_path("sim_output.json"))
    if not out_file.exists():
        return JsonResponse({"outputs": []})
    try:
        data = json.loads(out_file.read_text())
    except Exception:
        data = {"outputs": [], "id": 0}

    since_id = request.GET.get("since_id")
    if since_id:
        filtered = [o for o in data.get("outputs", []) if int(o.get("id", "0")) > int(since_id)]
        return JsonResponse({"outputs": filtered})
    return JsonResponse(data)

##########################################
# CMD NOT MINIMIZED WHEN RUNNING BACKEND #
##########################################

"""
@csrf_exempt
def start_backend(request):
    try:
        # Get the frontend directory (translator/)
        frontend_dir = Path(__file__).resolve().parents[1]

        # Go up to project root, then into backend_server
        backend_dir = frontend_dir.parents[2] / "Capstone-Project-ED-Simulation" / "reverie" / "backend_server"

        if not backend_dir.exists():
            return JsonResponse({
                "ok": False,
                "error": f"Backend directory not found: {backend_dir}"
            })

        # Determine OS and launch backend appropriately
        if sys.platform == "win32":
            # Windows: open a new console
            subprocess.Popen(
                ["python", "reverie.py"],
                cwd=str(backend_dir),
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            # Linux / macOS: run in background, suppress output
            subprocess.Popen(
                [sys.executable, "reverie.py"],
                cwd=str(backend_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

        return JsonResponse({"ok": True})

    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)})
"""

######################################
# CMD MINIMIZED WHEN RUNNING BACKEND #
######################################

from django.conf import settings
import psutil

@csrf_exempt
def start_backend(request, origin, target):
    try:
        backend_dir = _resolve_backend_dir()

        if not backend_dir.exists():
            return JsonResponse({
                "ok": False,
                "error": f"Backend directory not found: {backend_dir}"
            })
        running_pids = _list_running_reverie_processes(backend_dir)
        if running_pids:
            return JsonResponse({
                "ok": running_pids[0],
                "backend_dir": str(backend_dir),
                "already_running": True,
                "running_pids": running_pids,
            })
        if check_if_file_exists(_temp_path("curr_step.json")): 
            os.remove(_temp_path("curr_step.json"))


        arguments = ["--frontend_ui", "yes", "--origin", origin, "--target", target]
        cmd = [sys.executable, "reverie.py"]
        cmd += arguments
        backend_env = os.environ.copy()
        backend_env.setdefault("PYTHONUTF8", "1")
        backend_env.setdefault("PYTHONIOENCODING", "utf-8")
        curr_sim = None
        if sys.platform == "win32":
            startup_info = subprocess.STARTUPINFO()
            startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup_info.wShowWindow = 2

            curr_sim = subprocess.Popen(
                cmd,
                cwd=str(backend_dir),
                env=backend_env,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                startupinfo=startup_info
            )
        elif sys.platform == "darwin":
            import shlex, json

            cmd_str = f"cd {shlex.quote(str(backend_dir))} && {shlex.quote(sys.executable)} reverie.py"
            applescript = f'tell application "Terminal" to do script {json.dumps(cmd_str)}'
            subprocess.Popen(["osascript", "-e", applescript])


        else:
            curr_sim = subprocess.Popen(
                cmd,
                cwd=str(backend_dir),
                env=backend_env,
            )
        start_wait = time.time()
        while (not check_if_file_exists(_temp_path("curr_step.json"))):
            if time.time() - start_wait > 20:
                break
            time.sleep(0.5)
        return JsonResponse({"ok": curr_sim.pid if curr_sim else True, "backend_dir": str(backend_dir)})

    except Exception as e:
        return JsonResponse({
            "ok": False,
            "error": str(e)
        })


def start_page(request):
    ui_mode = str(request.GET.get("ui_mode", "auto")).strip().lower()
    if ui_mode not in {"auto", "user"}:
        ui_mode = "auto"
    return render(request, "../templates/home/start_simulation.html", {"ui_mode": ui_mode})

import csv
import numpy as np
import pandas as pd


def live_dashboard_page(request):
    return render(request, "home/live_dashboard.html")


def live_dashboard_api(request):
    """Return the latest sim_status.json data for the live dashboard."""
    # Auto-detect active sim code
    try:
        with open(_temp_path("curr_sim_code.json")) as f:
            sim_code = json.load(f).get("sim_code", "")
    except (FileNotFoundError, json.JSONDecodeError):
        return JsonResponse({"error": "No active simulation found."}, status=404)

    status_path = _storage_path(sim_code, "sim_status.json")
    if not os.path.exists(status_path):
        return JsonResponse({"error": "Waiting for simulation data..."}, status=404)

    try:
        with open(status_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return JsonResponse({"error": "Status file unreadable, retrying..."}, status=503)

    try:
        status_step = int(data.get("step"))
    except (TypeError, ValueError):
        status_step = None
    data["runtime_sync"] = _build_runtime_sync(sim_code, status_step=status_step)

    # Optionally include completed patient stage times
    if request.GET.get("include_stages") == "true":
        csv_path = _storage_path(sim_code, "reverie", "completed_patient_stage_times.csv")
        stages = []
        if os.path.exists(csv_path):
            try:
                with open(csv_path, newline="") as f:
                    reader = csv.DictReader(f)
                    hide = {"original_stage1_minutes",
                            "original_stage2_minutes",
                            "original_stage3_minutes"}
                    for row in reader:
                        stages.append({k: v for k, v in row.items()
                                       if k not in hide})
            except Exception:
                pass
        data["completed_stages"] = stages

    return JsonResponse(data)


def data_api(request):
    sim_code = request.GET.get("sim_code") or _current_sim_code()
    if not sim_code:
        return JsonResponse({
            "ok": False,
            "error": "No sim_code was provided and no active simulation was found.",
        }, status=400)
    csv_path = _storage_path(sim_code, "reverie", "state_times.csv")
    if not os.path.exists(csv_path):
        return JsonResponse({
            "ok": False,
            "error": f"state_times.csv was not found for sim_code={sim_code}. Run backend save/fin first.",
            "sim_code": sim_code,
            "path": csv_path,
        }, status=404)

    df = pd.read_csv(csv_path)

    # Convert minutes → hours
    time_cols = [
        "WAITING_FOR_TRIAGE", "TRIAGE", "WAITING_FOR_NURSE",
        "WAITING_FOR_FIRST_ASSESSMENT", "WAITING_FOR_TEST", "GOING_FOR_TEST", "WAITING_FOR_RESULT",
        "WAITING_FOR_DOCTOR", "LEAVING"
    ]
    time_cols = [col for col in time_cols if col in df.columns]
    if not time_cols or "CTAS" not in df.columns:
        return JsonResponse({
            "ok": False,
            "error": f"state_times.csv for sim_code={sim_code} does not contain the expected columns.",
            "sim_code": sim_code,
            "path": csv_path,
            "columns": list(df.columns),
        }, status=422)
    df[time_cols] = df[time_cols] / 60.0

    stages = {
        "waiting": ["WAITING_FOR_TRIAGE", "TRIAGE", "WAITING_FOR_NURSE", "WAITING_FOR_FIRST_ASSESSMENT"],
        "treatment": ["WAITING_FOR_TEST", "GOING_FOR_TEST", "WAITING_FOR_RESULT"],
        "ed": ["WAITING_FOR_DOCTOR", "LEAVING"]
    }
    stages = {
        stage: [col for col in cols if col in df.columns]
        for stage, cols in stages.items()
    }

    result = {}

    for stage, cols in stages.items():
        result[stage] = {}

        for ctas in sorted(df["CTAS"].dropna().unique()):
            values = (
                df[df["CTAS"] == ctas][cols]
                .stack()
                .dropna()
                .values
            )

            if len(values) == 0:
                continue

            counts, bin_edges = np.histogram(values, bins=20)

            labels = [
                f"{bin_edges[i]:.1f}-{bin_edges[i+1]:.1f}"
                for i in range(len(bin_edges) - 1)
            ]

            result[stage][f"CTAS {int(ctas)}"] = {
                "bins": labels,
                "counts": counts.tolist()
            }

    return JsonResponse(result)

def data_page(request):
    return render(
        request,
        "../templates/home/data_visualization.html",
        {"current_sim_code": _current_sim_code("")},
    )

@csrf_exempt
def save_simulation_settings(request):
    """
    Save frontend-selected simulation parameters before starting backend.
    """

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required"}, status=400)

    try:
        payload = json.loads(request.body)

        sim_code = "ed_sim_n5"

        meta_path = _storage_path(sim_code, "reverie", "meta.json")

        if not os.path.exists(meta_path):
            return JsonResponse({"ok": False, "error": "meta.json not found"}, status=404)

        with open(meta_path, "r") as f:
            meta = json.load(f)

        allowed_keys = {
            "arrival_profile_mode",
            "fill_injuries",
            "preload_waiting_room_patients",
            "doctor_starting_amount",
            "triage_starting_amount",
            "bedside_starting_amount",
            "patient_rate_modifier",
            "priority_factor",
            "testing_time",
            "testing_result_time",
            "lab_capacity",
            "lab_turnaround_minutes",
            "imaging_capacity",
            "imaging_turnaround_minutes",
            "boarding_timeout_minutes",
            "add_patient_threshold",
            "seed",
            "patient_walkout_probability",
            "patient_walkout_check_minutes",
            "patient_post_discharge_linger_probability",
            "patient_post_discharge_linger_minutes",
            "simulate_hospital_admission",
            "admission_boarding_minutes_min",
            "admission_boarding_minutes_max",
        }

        for key in allowed_keys:
            if key in payload:
                meta[key] = payload[key]

        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        return JsonResponse({"ok": True})

    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)
    
@csrf_exempt
def force_shutdown(request):
    try:
        data = json.loads(request.body)
        pid = int(data.get("pid"))

        if not pid:
            return JsonResponse({"ok": False, "error": "No PID provided"}, status=400)

        file_path = Path(_temp_path("sim_output.json"))
        file_path.unlink(missing_ok=True)

        proc = psutil.Process(pid)
        proc.kill()
        proc.wait(timeout=3)

        return JsonResponse({"ok": True})

    except psutil.NoSuchProcess:
        return JsonResponse({"ok": False, "error": "Process already dead"})

    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


def _parse_json_body(request):
    try:
        return json.loads(request.body or b"{}")
    except Exception as exc:
        raise ApiError(f"Invalid JSON payload: {exc}", status_code=400, error_code="INVALID_SCHEMA")


def _json_ok(data: dict, *, status: int = 200):
    return JsonResponse({"ok": True, "data": data}, status=status)


def _json_error(exc: ApiError):
    return JsonResponse(
        {
            "ok": False,
            "error": str(exc),
            "error_code": getattr(exc, "error_code", "INVALID_REQUEST"),
            "message": str(exc),
            "field_errors": getattr(exc, "field_errors", None) or [],
        },
        status=getattr(exc, "status_code", 400),
    )


@csrf_exempt
def api_mode_user_encounter_start(request):
    if request.method != "POST":
        return _json_error(ApiError("POST required", status_code=405, error_code="METHOD_NOT_ALLOWED"))
    if _backend_mode() != "user":
        return _json_error(ApiError("User mode requires restarting backend with EDSIM_MODE=user", status_code=409, error_code="MODE_MISMATCH"))

    try:
        payload = _parse_json_body(request)
        result = start_encounter(payload)
        return _json_ok(result)
    except ApiError as exc:
        return _json_error(exc)
    except Exception as exc:
        return _json_error(ApiError(str(exc), status_code=500, error_code="INTERNAL_ERROR"))


@csrf_exempt
def api_ed_handoff_request(request):
    if request.method != "POST":
        return _json_error(ApiError("POST required", status_code=405, error_code="METHOD_NOT_ALLOWED"))

    try:
        payload = _parse_json_body(request)
        result = request_handoff(payload)
        return _json_ok(result)
    except ApiError as exc:
        return _json_error(exc)
    except Exception as exc:
        return _json_error(ApiError(str(exc), status_code=500, error_code="INTERNAL_ERROR"))


@csrf_exempt
def api_ed_handoff_complete(request):
    if request.method != "POST":
        return _json_error(ApiError("POST required", status_code=405, error_code="METHOD_NOT_ALLOWED"))

    try:
        payload = _parse_json_body(request)
        result = complete_handoff(payload)
        return _json_ok(result)
    except ApiError as exc:
        return _json_error(exc)
    except Exception as exc:
        return _json_error(ApiError(str(exc), status_code=500, error_code="INTERNAL_ERROR"))


def api_ed_queue_snapshot(request):
    if request.method != "GET":
        return _json_error(ApiError("GET required", status_code=405, error_code="METHOD_NOT_ALLOWED"))

    try:
        result = queue_snapshot()
        return _json_ok(result)
    except ApiError as exc:
        return _json_error(exc)
    except Exception as exc:
        return _json_error(ApiError(str(exc), status_code=500, error_code="INTERNAL_ERROR"))


@csrf_exempt
def api_mode_user_chat_turn(request):
    if request.method != "POST":
        return _json_error(ApiError("POST required", status_code=405, error_code="METHOD_NOT_ALLOWED"))
    if _backend_mode() != "user":
        return _json_error(ApiError("User mode requires restarting backend with EDSIM_MODE=user", status_code=409, error_code="MODE_MISMATCH"))

    try:
        payload = _parse_json_body(request)
        message = payload.get("message", "")
        result = user_mode_chat_turn(message)
        return _json_ok(result)
    except ApiError as exc:
        return _json_error(exc)
    except Exception as exc:
        return _json_error(ApiError(str(exc), status_code=500, error_code="INTERNAL_ERROR"))


def api_mode_user_session_status(request):
    if request.method != "GET":
        return _json_error(ApiError("GET required", status_code=405, error_code="METHOD_NOT_ALLOWED"))
    if _backend_mode() != "user":
        return _json_error(ApiError("User mode requires restarting backend with EDSIM_MODE=user", status_code=409, error_code="MODE_MISMATCH"))

    try:
        result = user_mode_session_status()
        return _json_ok(result)
    except ApiError as exc:
        return _json_error(exc)
    except Exception as exc:
        return _json_error(ApiError(str(exc), status_code=500, error_code="INTERNAL_ERROR"))


@csrf_exempt
def api_mode_user_session_reset(request):
    if request.method != "POST":
        return _json_error(ApiError("POST required", status_code=405, error_code="METHOD_NOT_ALLOWED"))
    if _backend_mode() != "user":
        return _json_error(ApiError("User mode requires restarting backend with EDSIM_MODE=user", status_code=409, error_code="MODE_MISMATCH"))

    try:
        result = reset_user_mode_session()
        return _json_ok(result)
    except ApiError as exc:
        return _json_error(exc)
    except Exception as exc:
        return _json_error(ApiError(str(exc), status_code=500, error_code="INTERNAL_ERROR"))
