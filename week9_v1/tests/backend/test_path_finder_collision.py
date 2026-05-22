import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_SERVER_DIR = REPO_ROOT / "reverie" / "backend_server"
if str(BACKEND_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_SERVER_DIR))

from path_finder import path_finder


def _assert_adjacent(path):
    for idx in range(1, len(path)):
        prev_x, prev_y = path[idx - 1]
        curr_x, curr_y = path[idx]
        assert abs(prev_x - curr_x) + abs(prev_y - curr_y) == 1


def test_path_finder_avoids_collision_tiles_on_corner_route():
    maze = [
        [0, 0, 1, 0, 0],
        [1, 0, 1, 0, 1],
        [1, 0, 0, 0, 1],
        [1, 1, 1, 0, 1],
        [1, 1, 1, 0, 0],
    ]
    start = (0, 0)
    end = (4, 4)

    path = path_finder(maze, start, end, "#")

    assert path[0] == start
    assert path[-1] == end
    _assert_adjacent(path)
    for tile_x, tile_y in path:
        assert maze[tile_y][tile_x] == 0


def test_path_finder_returns_stationary_path_for_same_tile():
    maze = [
        [0, 0],
        [0, 0],
    ]

    path = path_finder(maze, (1, 1), (1, 1), "#")

    assert path == [(1, 1)]
