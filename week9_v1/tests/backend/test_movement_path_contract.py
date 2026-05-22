import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_SERVER_DIR = REPO_ROOT / "reverie" / "backend_server"
if str(BACKEND_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_SERVER_DIR))

from reverie import _coerce_step_movement_path


def test_movement_path_stationary_keeps_single_tile():
    maze = [
        [0, 0, 0],
        [0, 0, 0],
        [0, 0, 0],
    ]
    path = _coerce_step_movement_path(maze, (1, 1), (1, 1))
    assert path == [[1, 1]]


def test_movement_path_changed_target_is_multi_tile_even_when_pathfinder_fails():
    maze = [
        [0, 1, 0],
        [1, 1, 1],
        [0, 1, 0],
    ]
    path = _coerce_step_movement_path(maze, (0, 0), (2, 2))
    assert len(path) >= 2
    assert path[0] == [0, 0]
    assert path[-1] == [2, 2]
