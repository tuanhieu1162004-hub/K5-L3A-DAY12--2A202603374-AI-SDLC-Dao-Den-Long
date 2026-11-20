"""Run consecutive randomized nights in one process."""

import argparse
import gc
import json
import random
import sys
import time
from pathlib import Path

from headless import CONTRACT_PATH, TICKS_PER_SECOND, initial_state, simulation_steps
from process_memory import rss_mb


class RandomFrames:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.move = [0, 0]

    def get(self, tick, default=None):
        if tick % 30 == 0:
            self.move = [self.rng.uniform(-1, 1), self.rng.uniform(-1, 1)]
        return {
            "move": self.move,
            "jump": self.rng.random() < .05,
            "dash": self.rng.random() < .03,
            "pulse": self.rng.random() < .02,
            "interact": self.rng.random() < .10,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--nights", required=True, type=int)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.nights < 1:
        parser.error("--nights must be positive")
    tuning = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["tuning"]
    start = time.perf_counter()
    results, crashes = [], 0
    mem_start = None
    for index in range(args.nights):
        night = index % 3 + 1
        seed = args.seed + index
        state = initial_state({}, seed, tuning, night)
        if mem_start is None:
            mem_start = rss_mb()
        duration = tuning[f"night{night}_duration_s"] * TICKS_PER_SECOND
        end = {}

        def capture(record):
            if record["type"] == "end":
                end.update(record)

        try:
            for _ in simulation_steps(capture, duration, duration, tuning, RandomFrames(seed), state):
                pass
            results.append(end["state"])
        except Exception as error:
            print(f"night {index + 1}: {error}", file=sys.stderr)
            crashes += 1
            results.append("crashed")
        del state
    gc.collect()
    report = {
        "nights": args.nights, "crashes": crashes, "results": results,
        "mem_start_mb": round(mem_start, 3), "mem_end_mb": round(rss_mb(), 3),
        "duration_s": round(time.perf_counter() - start, 3),
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return int(crashes != 0)


if __name__ == "__main__":
    raise SystemExit(main())
