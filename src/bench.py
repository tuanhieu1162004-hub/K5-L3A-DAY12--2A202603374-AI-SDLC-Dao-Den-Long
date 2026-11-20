"""Render the standard Ticket-04 benchmark scene and measure frame times."""

import argparse
import json
import math
import platform
import random
import time
from pathlib import Path
from types import SimpleNamespace

STARTED = time.perf_counter()

from panda3d.core import PandaSystem, loadPrcFileData

from headless import move_shades
from panda_game import LanternIsland
from process_memory import rss_mb


def distributed_points(rng, count, radius, height):
    rotation = rng.uniform(0, math.tau)
    golden_angle = math.pi * (3 - math.sqrt(5))
    for index in range(count):
        distance = radius * math.sqrt((index + .5) / count)
        angle = rotation + index * golden_angle
        yield [distance * math.cos(angle), height, distance * math.sin(angle)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--duration", required=True, type=float)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if not math.isfinite(args.duration) or args.duration <= 0:
        parser.error("--duration must be positive and finite")
    loadPrcFileData("benchmark", "sync-video false\nwin-size 1280 720\nfullscreen false")
    app = LanternIsland(benchmark=True)
    app.screen = "benchmark"
    app.taskMgr.remove("game loop")
    state = app.snapshot
    rng = random.Random(args.seed)
    state["shades"] = [
        {"id": f"S{i}", "pos": point, "state": "wander", "state_until": 0}
        for i, point in enumerate(distributed_points(rng, 200, 39, 1), start=1)
    ]
    state["motes"] = [
        {"id": f"M{i}", "pos": point, "kind": "random", "ttl_s": None}
        for i, point in enumerate(distributed_points(rng, 100, 38, 0), start=1)
    ]
    for lantern in state["lanterns"][:3]:
        lantern.update(lit=True, fuel=100, ever_lit=True)
    # move_shades consumes the simulation's integer fuel representation.
    lanterns = [{**entry, "fuel": round(entry["fuel"] * 60)} for entry in state["lanterns"]]
    scene_start = time.perf_counter()

    def frame(elapsed):
        task = SimpleNamespace(time=elapsed, cont=None)
        app.update_game(task)
        angle = math.tau * elapsed / 15
        app.camera.setPos(30 * math.cos(angle), 30 * math.sin(angle), 15)
        app.camera.lookAt(0, 0, 0)
        app.taskMgr.step()

    frame(0)
    load_ms = (time.perf_counter() - STARTED) * 1000
    measure_start = scene_start + 3
    end = measure_start + args.duration
    previous = time.perf_counter()
    frame_times = []
    peak = rss_mb()
    next_sample = measure_start
    while previous < end:
        elapsed = previous - scene_start
        target_tick = int(elapsed * 60)
        while state["sim_tick"] < target_tick:
            state["sim_tick"] += 1
            move_shades(state["sim_tick"], state["shades"], state["player"]["pos"],
                        lanterns, app.tuning, chase_enabled=False)
        frame(elapsed)
        now = time.perf_counter()
        if previous >= measure_start and now <= end:
            frame_times.append((now - previous) * 1000)
        if now >= next_sample:
            peak = max(peak, rss_mb())
            next_sample = now + .1
        previous = now
    gsg = app.win.getGsg()
    renderer = f"Panda3D {PandaSystem.getVersionString()} / {gsg.getDriverRenderer()}"
    app.destroy()
    if not frame_times:
        parser.error("measurement window produced no complete frames")
    ordered = sorted(frame_times)
    tail = ordered[-max(1, math.ceil(.01 * len(ordered))):]
    report = {
        "contract_version": "1.3",
        "avg_fps": round(1000 * len(ordered) / sum(ordered), 3),
        "p1_low_fps": round(1000 * len(tail) / sum(tail), 3),
        "frame_ms_p95": round(ordered[math.ceil(.95 * len(ordered)) - 1], 3),
        "frames": len(ordered), "load_ms": round(load_ms, 3),
        "peak_mem_mb": round(peak, 3), "vsync_off": True,
        "renderer": renderer, "os": platform.platform(),
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
