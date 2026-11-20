"""Run representative Ticket-02 scenarios through the public headless CLI."""

import json
import math
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_night(night, ticks, scenario=None, frames=(), interval=1):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)
        scenario_file, inputs_file, output = (path / name for name in ("scenario", "inputs", "out"))
        scenario_file.write_text(json.dumps({
            "random_motes": False, "random_shades": False, "random_drifters": False, "charms": [],
            **(scenario or {}),
        }))
        inputs_file.write_text(json.dumps({"frames": frames}))
        subprocess.run([
            sys.executable, "-B", str(ROOT / "src/headless.py"),
            "--seed", "42", "--night", str(night), "--ticks", str(ticks),
            "--snapshot-every", str(interval), "--scenario", str(scenario_file),
            "--inputs", str(inputs_file), "--out", str(output),
        ], check=True)
        return [json.loads(line) for line in output.read_text().splitlines()]


def snapshots(rows):
    return {row["tick"]: row for row in rows if row["type"] == "snapshot"}


class PhaseTwo(unittest.TestCase):
    def test_maps_and_spawn_schedule(self):
        for night, first, count in ((1, 300, 2), (2, 420, 1), (3, 360, 1)):
            with self.subTest(night=night):
                rows = run_night(night, first, {"random_shades": True, "random_motes": True}, interval=first)
                initial, last = snapshots(rows).values()
                self.assertEqual(len(initial["lanterns"]), night + 4)
                self.assertEqual(initial["motes_active"], 30 if night == 3 else 24)
                self.assertEqual(initial["shades"], [])
                spawned = [row for row in rows if row.get("name") == "shade_spawned"]
                self.assertEqual([row["tick"] for row in spawned], [first] * count)
                self.assertTrue(all(shade["state"] == "spawning" for shade in last["shades"]))

    def test_bridge_pad_and_fall(self):
        bridge = run_night(2, 180, {"player": {"pos": [27, 0, 0]}}, [{"tick": 0, "move": [1, 0]}], 180)
        self.assertEqual(snapshots(bridge)[180]["player"]["pos"], [45, 0, 0])
        pad = run_night(2, 87, {"player": {"pos": [20, 0, 18]}}, [{"tick": 0, "move": [-1, 0]}], 87)
        x, y, z = snapshots(pad)[87]["player"]["pos"]
        self.assertEqual(y, 0)
        self.assertLess(math.hypot(x - 70, z), 28)
        fall = run_night(1, 1, {"player": {"pos": [40, 0, 0]}}, [{"tick": 0, "move": [1, 0]}])
        hit = next(row["data"] for row in fall if row.get("name") == "player_hit")
        self.assertEqual((hit["by"], hit["flames"], hit["lost"]), ("fall", 2, 0))

    def test_pause(self):
        args = json.loads((ROOT / "docs/proof/phase-2/pause-inputs.json").read_text())
        rows = run_night(1, 5, frames=args["frames"])
        self.assertEqual([row["sim_tick"] for row in snapshots(rows).values()], [0, 1, 1, 1, 1, 2])
        self.assertEqual([row["tick"] for row in rows if row.get("name") in ("paused", "resumed")], [2, 5])

    def test_charm_and_dash(self):
        frames = [{"tick": 1, "dash": True}, {"tick": 12, "dash": False}, {"tick": 13, "dash": True}]
        rows = run_night(2, 14, {"charms": [{"pos": [0, 0, 0]}]}, frames)
        self.assertEqual([row["tick"] for row in rows if row.get("name") == "dash"], [2, 14])
        self.assertEqual(snapshots(rows)[2]["player"]["vel"], [0, 0, 14])

    def test_drifter_steals_and_drops(self):
        rows = run_night(2, 2, {"player": {"carried": 5}, "drifters": [{"pos": [1, 0, 0]}]},
                         [{"tick": 1, "pulse": True}])
        events = [row["name"] for row in rows if row["type"] == "event"]
        self.assertEqual(events, ["night_start", "drifter_steal", "pulse", "drifter_drop"])
        self.assertEqual([mote["kind"] for mote in snapshots(rows)[2]["motes"]], ["dropped"] * 3)
        spawned = run_night(2, 1200, {"random_drifters": True}, interval=1200)
        self.assertEqual(snapshots(spawned)[1200]["drifters"][0]["id"], "D1")

    def test_wind_is_seeded(self):
        rows = run_night(3, 2100, interval=300)
        self.assertEqual(rows, run_night(3, 2100, interval=300))
        wind = snapshots(rows)
        self.assertTrue(wind[1800]["wind"]["active"])
        self.assertFalse(wind[2100]["wind"]["active"])
        x, _, z = wind[2100]["player"]["pos"]
        self.assertAlmostEqual(math.hypot(x, z), 10, places=2)

    def test_dawn_score_and_performance(self):
        proof = ROOT / "docs/proof/phase-1"
        scenario = json.loads((proof / "final-lantern.json").read_text())
        scenario["time_left_s"] = 3 / 60
        scenario["lanterns"][4]["deposited"] = 8
        rows = run_night(1, 10, scenario, [{"tick": 0, "interact": True}])
        self.assertEqual(snapshots(rows)[1]["state"], "playing")
        self.assertEqual(rows[-1], {"type": "end", "ticks": 3, "state": "won", "score": 1005})
        start = time.monotonic()
        rows = run_night(3, 21600, {"time_left_s": 360, "wind_enabled": False}, interval=300)
        self.assertEqual(rows[-1]["ticks"], 21600)
        self.assertLess(time.monotonic() - start, 30)

    def test_out_relight_and_capacity(self):
        scenario = {"player":{"carried":5}, "lanterns":[{"id":"L1","pos":[0,0,0],"lit":True,"fuel":1/60}]}
        rows = run_night(1, 1, scenario, [{"tick":0,"interact":True}])
        self.assertEqual([r["name"] for r in rows if r["type"]=="event"],
                         ["night_start","lantern_out","deposit","lantern_lit"])
        snap = snapshots(rows)[1]
        self.assertEqual(snap["player"]["capacity"], 12)
        self.assertEqual(snap["lanterns"][0]["fuel"], 100)
        self.assertEqual(snap["lanterns"][0]["relit_count"], 1)
        self.assertEqual(snap["score"], 65)

    def test_drain_and_refuel(self):
        scenario = {"lanterns":[{"id":"L1","pos":[10,0,0],"lit":True,"fuel":29}],
                    "shades":[{"pos":[10,1,0],"state":"wander"}]}
        rows = run_night(1, 61, scenario, interval=61)
        drain = next(r for r in rows if r.get("name")=="fuel_drain")
        self.assertEqual((drain["tick"], drain["data"]["fuel"]), (61, 23.0))
        scenario["player"] = {"pos":[8,0,0],"carried":1}
        scenario["shades"][0].update(state="drain", target_lantern_id="L1")
        rows = run_night(1, 1, scenario, [{"tick":0,"interact":True}])
        snap = snapshots(rows)[1]
        self.assertEqual(snap["shades"][0]["state"], "recoil")
        self.assertEqual(snap["score"], 5)
        self.assertTrue(any(r.get("name")=="refuel" for r in rows))

    def test_dawn_prioritizes_no_flames(self):
        rows = run_night(1, 1, {"time_left_s":1/60, "player":{"flames":1},
                                "shades":[{"pos":[0,1,0]}],
                                "lanterns":[{"id":f"L{i}","lit":True} for i in range(1,6)]})
        self.assertEqual(next(r["data"]["reason"] for r in rows if r.get("name")=="game_over"), "no_flames")


if __name__ == "__main__":
    unittest.main(verbosity=2)
