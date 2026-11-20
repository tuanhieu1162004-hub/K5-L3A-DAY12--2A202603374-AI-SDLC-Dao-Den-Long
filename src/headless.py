"""Run the fixed-step simulation without opening a window."""

import argparse
import json
import math
import random
import sys
from pathlib import Path


TICKS_PER_SECOND = 60
JUMP_SPEED = 6
GRAVITY = 18
CONTRACT_PATH = Path(__file__).resolve().parents[1] / "game.contract.json"
LANTERN_POSITIONS = (
    (0, 0, 12),
    (11, 0, 4),
    (7, 0, -10),
    (-7, 0, -10),
    (-11, 0, 4),
)


def write_record(output, **record):
    if output is not None:
        output.write(json.dumps(record, separators=(",", ":")) + "\n")


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def position(value):
    if not isinstance(value, list) or len(value) != 3 or not all(map(finite_number, value)):
        raise ValueError("pos must contain three finite numbers")
    return value.copy()


def count(value):
    if type(value) is not int or value < 0:
        raise ValueError("expected a nonnegative integer")
    return value


def objects(value):
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("expected an array of objects")
    return value


def initial_state(scenario, seed, tuning):
    if not isinstance(scenario, dict):
        raise ValueError("scenario must be an object")

    player_data = scenario.get("player", {})
    if not isinstance(player_data, dict):
        raise ValueError("player must be an object")
    player = {
        "pos": position(player_data.get("pos", [0, 0, 0])),
        "flames": count(player_data.get("flames", tuning["flames"])),
        "carried": count(player_data.get("carried", 0)),
    }
    lanterns = {
        f"L{index}": {"id": f"L{index}", "pos": list(point), "lit": False, "deposited": 0}
        for index, point in enumerate(LANTERN_POSITIONS, start=1)
    }
    for update in objects(scenario.get("lanterns", [])):
        lantern_id = update.get("id")
        if not isinstance(lantern_id, str) or lantern_id not in lanterns:
            raise ValueError("lantern id must be L1 through L5")
        lantern = lanterns[lantern_id]
        if "pos" in update:
            lantern["pos"] = position(update["pos"])
        if "deposited" in update:
            lantern["deposited"] = count(update["deposited"])
        if "lit" in update:
            if type(update["lit"]) is not bool:
                raise ValueError("lantern lit must be a boolean")
            lantern["lit"] = update["lit"]

    for flag in ("random_motes", "random_shades"):
        if flag in scenario and type(scenario[flag]) is not bool:
            raise ValueError(f"{flag} must be a boolean")
    mote_points = scenario.get("motes", [])
    if not isinstance(mote_points, list):
        raise ValueError("motes must be an array of positions")
    if "motes" not in scenario and scenario.get("random_motes", True):
        rng = random.Random(seed)
        for _ in range(30):
            angle = rng.uniform(0, math.tau)
            radius = rng.uniform(2, 14)
            mote_points.append([radius * math.cos(angle), 0, radius * math.sin(angle)])
    motes = [
        {"id": f"M{index}", "pos": position(point)}
        for index, point in enumerate(mote_points, start=1)
    ]

    shade_data = objects(scenario.get("shades", []))
    if "shades" not in scenario and scenario.get("random_shades", True):
        rng = random.Random(f"shades:{seed}")
        shade_data = []
        for index in range(2):
            angle = rng.uniform(0, math.tau) + index * math.pi
            shade_data.append({"pos": [10 * math.cos(angle), 1, 10 * math.sin(angle)]})

    shades = []
    used_ids = set()
    for shade in shade_data:
        if "id" in shade:
            shade_id = shade["id"]
            if not isinstance(shade_id, str) or shade_id in used_ids:
                raise ValueError("shade ids must be unique strings")
            used_ids.add(shade_id)
    next_id = 1
    for shade in shade_data:
        shade_id = shade.get("id")
        if shade_id is None:
            while f"S{next_id}" in used_ids:
                next_id += 1
            shade_id = f"S{next_id}"
            next_id += 1
        shades.append({"id": shade_id, "pos": position(shade.get("pos")), "state": "chase"})

    duration = scenario.get("time_left_s", tuning["night1_duration_s"])
    if not finite_number(duration) or duration < 0:
        raise ValueError("time_left_s must be a nonnegative finite number")
    return player, list(lanterns.values()), motes, shades, duration


def rounded_entity(entity):
    return {**entity, "pos": [round(value, 3) for value in entity["pos"]]}


def collect_motes(output, tick, player, motes, tuning):
    remaining = []
    x, _, z = player["pos"]
    for mote in motes:
        mote_x, _, mote_z = mote["pos"]
        distance = math.hypot(mote_x - x, mote_z - z)
        if player["carried"] < tuning["carry_capacity"] and distance <= tuning["pickup_radius"]:
            player["carried"] += 1
            write_record(
                output, type="event", tick=tick, name="mote_picked",
                data={"carried": player["carried"]},
            )
        else:
            remaining.append(mote)
    return remaining


def deposit_light(output, tick, player, lanterns, tuning):
    x, _, z = player["pos"]
    nearest = None
    nearest_distance = math.inf
    cost = tuning["lantern_cost"]
    for lantern in lanterns:
        if lantern["lit"] or lantern["deposited"] >= cost:
            continue
        lantern_x, _, lantern_z = lantern["pos"]
        distance = math.hypot(lantern_x - x, lantern_z - z)
        if distance <= tuning["interact_radius"] and distance < nearest_distance:
            nearest, nearest_distance = lantern, distance

    if nearest is None or player["carried"] == 0:
        return 0

    amount = min(player["carried"], cost - nearest["deposited"])
    player["carried"] -= amount
    nearest["deposited"] += amount
    write_record(
        output, type="event", tick=tick, name="deposit",
        data={"lantern_id": nearest["id"], "amount": amount, "deposited": nearest["deposited"]},
    )
    if nearest["deposited"] < cost:
        return 0

    nearest["lit"] = True
    write_record(
        output, type="event", tick=tick, name="lantern_lit",
        data={"lantern_id": nearest["id"]},
    )
    return tuning["score"]["per_lantern"]


def ground_distance(first, second):
    return math.hypot(first[0] - second[0], first[2] - second[2])


def step_toward(origin, target, distance):
    gap = ground_distance(origin, target)
    if gap == 0:
        return [origin[0] - min(distance, 0), origin[1], origin[2]]
    ratio = min(distance, gap) / gap
    return [
        origin[0] + (target[0] - origin[0]) * ratio,
        origin[1],
        origin[2] + (target[2] - origin[2]) * ratio,
    ]


def pulse_shades(output, tick, player, shades, stunned_until, tuning):
    player["carried"] -= tuning["pulse_cost"]
    stunned_ids = []
    for shade in shades:
        if ground_distance(shade["pos"], player["pos"]) <= tuning["pulse_radius"]:
            shade["pos"] = step_toward(shade["pos"], player["pos"], -tuning["pulse_push_m"])
            stunned_until[shade["id"]] = tick + math.ceil(tuning["pulse_stun_s"] * TICKS_PER_SECOND)
            stunned_ids.append(shade["id"])
    write_record(output, type="event", tick=tick, name="pulse", data={"stunned_ids": stunned_ids})
    return len(stunned_ids) * tuning["score"]["per_stun"]


def move_shades(tick, shades, player_position, lanterns, stunned_until, tuning):
    radius = tuning["safe_radius"]
    safe_centers = [lantern["pos"] for lantern in lanterns if lantern["lit"]]
    protected = any(ground_distance(center, player_position) <= radius for center in safe_centers)
    step = tuning["shade_speed"] / TICKS_PER_SECOND
    contact = False
    for shade in shades:
        shade["state"] = "chase"
        if tick < stunned_until.get(shade["id"], 0):
            shade["state"] = "stunned"
            continue

        origin = shade["pos"]
        threat = next((center for center in safe_centers if ground_distance(center, origin) <= radius), None)
        if threat is not None:
            shade["pos"] = step_toward(origin, threat, -step)
            shade["state"] = "flee"
            continue

        candidate = step_toward(origin, player_position, step)
        if any(ground_distance(center, candidate) <= radius for center in safe_centers):
            shade["state"] = "flee"
        else:
            shade["pos"] = candidate
        if not protected and ground_distance(shade["pos"], player_position) <= tuning["shade_hit_radius"]:
            contact = True
    return contact


def load_inputs(path):
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("frames"), list):
        raise ValueError("expected a frames array")

    frames = {}
    previous_tick = -1
    for frame in document["frames"]:
        tick = frame.get("tick") if isinstance(frame, dict) else None
        if type(tick) is not int or tick <= previous_tick:
            raise ValueError("frame ticks must be nonnegative integers in strictly increasing order")
        if "move" in frame:
            move = frame["move"]
            if not isinstance(move, list) or len(move) != 2 or not all(
                type(value) in (int, float) and -1 <= value <= 1 for value in move
            ):
                raise ValueError(f"tick {tick}: move must contain two numbers between -1 and 1")
        if "cam_yaw_deg" in frame and not finite_number(frame["cam_yaw_deg"]):
            raise ValueError(f"tick {tick}: cam_yaw_deg must be a finite number")
        for button in ("jump", "interact", "pulse", "dash"):
            if button in frame and type(frame[button]) is not bool:
                raise ValueError(f"tick {tick}: {button} must be a boolean")
        frames[tick] = frame
        previous_tick = tick
    return frames


def move_player(position, move, yaw_degrees, speed):
    x, z = move
    yaw = math.radians(yaw_degrees % 360)
    sine, cosine = math.sin(yaw), math.cos(yaw)
    step = speed / (TICKS_PER_SECOND * max(1, math.hypot(x, z)))
    position[0] += (x * cosine + z * sine) * step
    position[2] += (-x * sine + z * cosine) * step


def simulation_steps(output, ticks, snapshot_every, tuning, frames, initial, island_radius=None):
    player, lanterns, motes, shades, duration = initial
    state = "playing"
    score = 0
    move, yaw = [0, 0], 0
    interact = False
    jump = False
    vertical_speed = 0
    pulse = False
    pulse_ready = hit_ready = 0
    stunned_until = {}
    for tick in range(ticks + 1):
        time_left = max(0, duration - tick / TICKS_PER_SECOND)
        if tick > 0:
            frame = frames.get(tick - 1, {})
            move = frame.get("move", move)
            yaw = frame.get("cam_yaw_deg", yaw)
            move_player(player["pos"], move, yaw, tuning["player_speed"])
            if island_radius is not None:
                x, _, z = player["pos"]
                radius = math.hypot(x, z)
                if radius > island_radius:
                    player["pos"][0] *= island_radius / radius
                    player["pos"][2] *= island_radius / radius
            next_jump = frame.get("jump", jump)
            if next_jump and not jump and player["pos"][1] == 0:
                vertical_speed = JUMP_SPEED
            jump = next_jump
            if player["pos"][1] > 0 or vertical_speed > 0:
                player["pos"][1] = max(0, player["pos"][1] + vertical_speed / TICKS_PER_SECOND)
                vertical_speed = vertical_speed - GRAVITY / TICKS_PER_SECOND if player["pos"][1] > 0 else 0
            remaining = collect_motes(output, tick, player, motes, tuning)
            score += (len(motes) - len(remaining)) * tuning["score"]["per_mote"]
            motes = remaining
            next_interact = frame.get("interact", interact)
            if next_interact and not interact:
                score += deposit_light(output, tick, player, lanterns, tuning)
            interact = next_interact

            next_pulse = frame.get("pulse", pulse)
            if next_pulse and not pulse and tick >= pulse_ready and player["carried"] >= tuning["pulse_cost"]:
                score += pulse_shades(output, tick, player, shades, stunned_until, tuning)
                pulse_ready = tick + math.ceil(tuning["pulse_cooldown_s"] * TICKS_PER_SECOND)
            pulse = next_pulse

            contact = move_shades(tick, shades, player["pos"], lanterns, stunned_until, tuning)
            if contact and tick >= hit_ready and player["flames"] > 0:
                player["flames"] -= 1
                dropped = math.floor(player["carried"] * tuning["hit_drop_ratio"])
                player["carried"] -= dropped
                hit_ready = tick + math.ceil(tuning["invuln_s"] * TICKS_PER_SECOND)
                write_record(
                    output, type="event", tick=tick, name="player_hit",
                    data={"by": "shade", "flames": player["flames"], "dropped": dropped},
                )

        reason = None
        if tick > 0:
            if all(lantern["lit"] for lantern in lanterns):
                state, reason = "won", "all_lit"
            elif player["flames"] == 0:
                state, reason = "lost", "no_flames"
            elif time_left <= 0:
                state, reason = "lost", "dawn"
        if reason:
            write_record(
                output, type="event", tick=tick, name="game_over",
                data={"result": state, "reason": reason},
            )
        if tick % snapshot_every == 0:
            snapshot = dict(
                type="snapshot", tick=tick, sim_tick=tick,
                state=state, time_left_s=time_left, score=score, player=rounded_entity(player),
                lanterns=[rounded_entity(lantern) for lantern in lanterns],
                shades=[rounded_entity(shade) for shade in shades],
                motes_active=len(motes), motes=[rounded_entity(mote) for mote in motes],
            )
            write_record(output, **snapshot)
            yield snapshot
        if state != "playing":
            break
    write_record(output, type="end", ticks=tick, state=state, score=score)


def simulate(output, ticks, snapshot_every, tuning, frames, initial):
    for _ in simulation_steps(output, ticks, snapshot_every, tuning, frames, initial):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--night", required=True, type=int, choices=[1])
    parser.add_argument("--ticks", required=True, type=int)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--scenario", type=Path)
    parser.add_argument("--snapshot-every", type=int, default=10)
    args = parser.parse_args()
    if args.ticks < 0 or args.snapshot_every < 1:
        parser.error("--ticks must be nonnegative and --snapshot-every must be positive")

    try:
        frames = load_inputs(args.inputs) if args.inputs else {}
    except (OSError, ValueError, OverflowError) as error:
        parser.error(f"invalid inputs: {error}")

    try:
        tuning = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["tuning"]
        try:
            scenario = json.loads(args.scenario.read_text(encoding="utf-8")) if args.scenario else {}
            initial = initial_state(scenario, args.seed, tuning)
        except (OSError, ValueError, OverflowError) as error:
            parser.error(f"invalid scenario: {error}")
        with args.out.open("w", encoding="utf-8", newline="\n") as output:
            simulate(output, args.ticks, args.snapshot_every, tuning, frames, initial)
    except OSError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
