"""Run the fixed-step simulation without opening a window."""

import argparse
import json
import math
import random
import sys
from pathlib import Path
from night_features import CHARM_DURATION, CHARM_POINTS, CHARM_RESPAWN, CHARM_SPEED
from night_maps import LANTERNS, MOTE_POINTS, PADS, SHADE_POINTS, ground_levels


TICKS_PER_SECOND = 60
SHADE_STATES = ("spawning", "wander", "chase", "recoil", "stunned")
JUMP_SPEED = 6
GRAVITY = 18
CONTRACT_PATH = Path(__file__).resolve().parents[1] / "game.contract.json"


def write_record(output, **record):
    if callable(output):
        output(record)
    elif output is not None:
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


def initial_state(scenario, seed, tuning, night=1):
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
    player_timers = {
        key: count(player_data.get(key, 0))
        for key in ("invuln_ticks", "dash_cd_ticks", "pulse_cd_ticks", "charm_ticks")
    }
    lanterns = {
        f"L{index}": {"id": f"L{index}", "pos": list(point), "lit": False, "deposited": 0}
        for index, point in enumerate(LANTERNS[night], start=1)
    }
    for update in objects(scenario.get("lanterns", [])):
        lantern_id = update.get("id")
        if not isinstance(lantern_id, str) or lantern_id not in lanterns:
            raise ValueError(f"unknown lantern id for night {night}")
        lantern = lanterns[lantern_id]
        if "pos" in update:
            lantern["pos"] = position(update["pos"])
        if "deposited" in update:
            lantern["deposited"] = count(update["deposited"])
        if "lit" in update:
            if type(update["lit"]) is not bool:
                raise ValueError("lantern lit must be a boolean")
            lantern["lit"] = update["lit"]

    for flag in ("random_motes", "random_shades", "random_drifters", "wind_enabled"):
        if flag in scenario and type(scenario[flag]) is not bool:
            raise ValueError(f"{flag} must be a boolean")
    mote_points = scenario.get("motes", [])
    if not isinstance(mote_points, list):
        raise ValueError("motes must be an array of positions")
    if "motes" not in scenario and scenario.get("random_motes", True):
        rng = random.Random(seed)
        mote_points = [list(point) for point in MOTE_POINTS[night]]
        rng.shuffle(mote_points)
    replenish_motes = "motes" not in scenario and scenario.get("random_motes", True)
    motes = [
        {"id": f"M{index}", "pos": position(point), "kind": "random", "expires": None}
        for index, point in enumerate(mote_points, start=1)
    ]

    shade_data = objects(scenario.get("shades", []))
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
        state = shade.get("state", "chase")
        if state not in SHADE_STATES:
            raise ValueError("unknown shade state")
        shades.append({"id": shade_id, "pos": position(shade.get("pos")), "state": state,
                       "state_until": 1 + count(shade.get("state_ticks_left", 0))})

    duration = scenario.get("time_left_s", tuning[f"night{night}_duration_s"])
    if not finite_number(duration) or duration < 0:
        raise ValueError("time_left_s must be a nonnegative finite number")
    shade_rng = random.Random(f"shades:{seed}") if scenario.get("random_shades", True) else None
    default_charms = [{"pos": point} for point in CHARM_POINTS[night]]
    charms = []
    for index, charm in enumerate(objects(scenario.get("charms", default_charms)), start=1):
        charm_id = charm.get("id", f"C{index}")
        available = charm.get("available", True)
        if not isinstance(charm_id, str) or type(available) is not bool:
            raise ValueError("invalid charm id or availability")
        charms.append({"id": charm_id, "pos": position(charm.get("pos")),
                       "ready": 1 + count(charm.get("respawn_ticks", CHARM_RESPAWN)) if not available else 0})
    drifters = []
    for index, entry in enumerate(objects(scenario.get("drifters", [])), start=1):
        drifter_id = entry.get("id", f"D{index}")
        state = entry.get("state", "idle")
        if not isinstance(drifter_id, str) or state not in ("idle", "chase", "flee", "removed"):
            raise ValueError("invalid drifter id or state")
        drifters.append({"id": drifter_id, "pos": position(entry.get("pos")), "state": state,
                         "stolen": count(entry.get("stolen", 0)),
                         "expires": count(entry.get("state_ticks_left", 240))})
    drifter_rng = random.Random(f"drifters:{seed}") if scenario.get("random_drifters", True) else None
    wind_rng = random.Random(f"wind:{seed}") if night == 3 and scenario.get("wind_enabled", True) else None
    return (player, list(lanterns.values()), motes, shades, duration, night, shade_rng,
            player_timers, charms, drifters, drifter_rng, wind_rng, replenish_motes)


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
    points = amount * tuning["score"]["per_mote"]
    if nearest["deposited"] < cost:
        return points

    nearest["lit"] = True
    write_record(
        output, type="event", tick=tick, name="lantern_lit",
        data={"lantern_id": nearest["id"]},
    )
    return points + tuning["score"]["per_lantern"]


def ground_distance(first, second):
    return math.hypot(first[0] - second[0], first[2] - second[2])


def spawn_shades(output, tick, sim_tick, night, player, shades, rng):
    first, interval, limit = {1: (5, 8, 6), 2: (7, 7, 8), 3: (6, 6, 10)}[night]
    elapsed = sim_tick - first * TICKS_PER_SECOND
    if rng is None or elapsed < 0 or elapsed % (interval * TICKS_PER_SECOND):
        return
    points = [
        point for point in SHADE_POINTS[night]
        if (night != 1 or ground_distance(point, player["pos"]) >= 15)
        and all(ground_distance(point, shade["pos"]) > 0 for shade in shades)
    ]
    count_to_spawn = min(len(points), limit - len(shades), 2 if night == 1 and elapsed == 0 else 1)
    next_id = 1
    used = {shade["id"] for shade in shades}
    for point in rng.sample(points, max(0, count_to_spawn)):
        while f"S{next_id}" in used:
            next_id += 1
        shade_id = f"S{next_id}"
        next_id += 1
        shades.append({"id": shade_id, "pos": list(point), "state": "spawning", "state_until": sim_tick + 1})
        write_record(output, type="event", tick=tick, name="shade_spawned", data={"id": shade_id})


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


def pulse_drifters(output, tick, sim_tick, player, drifters, motes, radius):
    for drifter in drifters:
        if ground_distance(player["pos"], drifter["pos"]) > radius:
            continue
        if drifter["state"] == "chase":
            drifter["state"], drifter["expires"] = "flee", sim_tick + 240
        elif drifter["state"] == "flee" and drifter["stolen"]:
            amount = drifter["stolen"]
            for index in range(amount):
                motes.append({"id": f"M-{drifter['id']}-{tick}-{index}", "pos": drifter["pos"].copy(),
                              "kind": "dropped", "expires": sim_tick + 600})
            drifter["stolen"], drifter["expires"] = 0, sim_tick + 120
            write_record(output, type="event", tick=tick, name="drifter_drop",
                         data={"drifter_id": drifter["id"], "amount": amount})


def move_drifters(output, tick, sim_tick, player, drifters):
    for drifter in sorted(drifters, key=lambda entry: entry["id"]):
        if drifter["state"] == "flee":
            drifter["pos"] = step_toward(drifter["pos"], player["pos"], -7 / TICKS_PER_SECOND)
            continue
        if player["carried"] >= 5 and ground_distance(player["pos"], drifter["pos"]) <= 15:
            drifter["state"] = "chase"
            drifter["pos"] = step_toward(drifter["pos"], player["pos"], 7 / TICKS_PER_SECOND)
            if ground_distance(player["pos"], drifter["pos"]) <= 1.2:
                amount = min(3, player["carried"])
                player["carried"] -= amount
                drifter.update(state="flee", stolen=amount, expires=sim_tick + 240)
                write_record(output, type="event", tick=tick, name="drifter_steal",
                             data={"drifter_id": drifter["id"], "amount": amount, "carried": player["carried"]})
        else:
            drifter["state"] = "idle"
            angle = sim_tick / TICKS_PER_SECOND
            drifter["pos"][0] += 2 * math.cos(angle) / TICKS_PER_SECOND
            drifter["pos"][2] += 2 * math.sin(angle) / TICKS_PER_SECOND


def pulse_shades(output, tick, sim_tick, player, shades, tuning):
    player["carried"] -= tuning["pulse_cost"]
    stunned_ids = []
    for shade in shades:
        if ground_distance(shade["pos"], player["pos"]) <= tuning["pulse_radius"]:
            shade["pos"] = step_toward(shade["pos"], player["pos"], -tuning["pulse_push_m"])
            shade["state"] = "stunned"
            shade["state_until"] = sim_tick + math.ceil(tuning["pulse_stun_s"] * TICKS_PER_SECOND)
            stunned_ids.append(shade["id"])
    write_record(output, type="event", tick=tick, name="pulse", data={"stunned_ids": stunned_ids})
    return len(stunned_ids) * tuning["score"]["per_stun"]


def move_shades(tick, shades, player_position, lanterns, tuning):
    radius = tuning["safe_radius"]
    safe_centers = [lantern["pos"] for lantern in lanterns if lantern["lit"]]
    protected = any(ground_distance(center, player_position) <= radius for center in safe_centers)
    step = tuning["shade_speed"] / TICKS_PER_SECOND
    contact = False
    for shade in shades:
        if tick < shade["state_until"] and shade["state"] in ("spawning", "stunned", "recoil", "wander"):
            continue
        shade["state"] = "chase"

        origin = shade["pos"]
        threat = next((center for center in safe_centers if ground_distance(center, origin) <= radius), None)
        if threat is not None:
            shade["pos"] = step_toward(origin, threat, -step)
            shade["state"] = "recoil"
            continue

        candidate = step_toward(origin, player_position, step)
        if any(ground_distance(center, candidate) <= radius for center in safe_centers):
            shade["state"] = "recoil"
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
        for button in ("jump", "interact", "pulse", "dash", "pause"):
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


def move_on_terrain(player, night, move, yaw, speed, jump, vertical_speed, launch, dashing, wind):
    position = player["pos"]
    previous = position.copy()
    x, y, z = previous
    grounded = vertical_speed == 0 and any(
        abs(y - level) < 1e-7 for level in ground_levels(night, x, z)
    )
    gravity = GRAVITY
    if grounded:
        for pad, target, vertical, horizontal in PADS[night]:
            if y == pad[1] and ground_distance(previous, pad) <= 1:
                distance = ground_distance(target, pad)
                launch = ((target[0] - pad[0]) * horizontal / distance,
                          (target[2] - pad[2]) * horizontal / distance)
                vertical_speed = vertical
                break
        else:
            if jump:
                vertical_speed = JUMP_SPEED
    if launch is None or dashing:
        move_player(position, move, yaw, speed)
    if launch is not None:
        gravity = 20
    if launch is not None and not dashing:
        position[0] += launch[0] / TICKS_PER_SECOND
        position[2] += launch[1] / TICKS_PER_SECOND
    if wind is not None:
        position[0] += 2 * math.cos(wind) / TICKS_PER_SECOND
        position[2] += 2 * math.sin(wind) / TICKS_PER_SECOND

    levels = ground_levels(night, position[0], position[2])
    if not levels and (grounded and vertical_speed == 0 or y < -2):
        position[:] = [0, 0, 0]
        return 0, None, True
    if night == 3 and math.hypot(position[0], position[2]) <= 2 and 6 <= y < 14:
        position[0], position[2] = x, z
        levels = ground_levels(night, x, z)
    if grounded and vertical_speed == 0:
        # Only gradual elevation changes can be climbed while grounded.
        walkable = [level for level in levels if abs(level - y) <= 0.15]
        if walkable:
            position[1] = max(walkable)
            return 0, None, False

    next_y = y + vertical_speed / TICKS_PER_SECOND
    landing = [level for level in levels if next_y <= level <= y]
    if vertical_speed <= 0 and landing and (not grounded or max(landing) == y):
        position[1] = max(landing)
        return 0, None, False
    position[1] = next_y
    return vertical_speed - gravity / TICKS_PER_SECOND, launch, False


def simulation_steps(output, ticks, snapshot_every, tuning, frames, initial):
    (player, lanterns, motes, shades, duration, night, shade_rng, timers,
     charms, drifters, drifter_rng, wind_rng, replenish_motes) = initial
    state = "playing"
    score = 0
    move, yaw = [0, 0], 0
    interact = False
    jump = False
    vertical_speed = 0
    launch = None
    pulse = False
    pulse_ready = timers["pulse_cd_ticks"] + 1
    hit_ready = timers["invuln_ticks"] + 1
    dash_ready = timers["dash_cd_ticks"] + 1
    charm_until = timers["charm_ticks"] + 1
    dash_until = 0
    dash = False
    dash_move, dash_yaw = [0, 1], 0
    velocity = [0, 0, 0]
    drifter_sequence = 0
    wind = None
    wind_direction = 0
    used_drifter_ids = {entry["id"] for entry in drifters}
    pause = False
    sim_tick = 0
    for tick in range(ticks + 1):
        if tick > 0:
            frame = frames.get(tick - 1, {})
            next_pause = frame.get("pause", pause)
            if next_pause and not pause:
                state = "playing" if state == "paused" else "paused"
                event = "paused" if state == "paused" else "resumed"
                write_record(output, type="event", tick=tick, name=event, data={})
            pause = next_pause
        if tick > 0 and state == "paused":
            move = frame.get("move", move)
            yaw = frame.get("cam_yaw_deg", yaw)
            jump = frame.get("jump", jump)
            interact = frame.get("interact", interact)
            pulse = frame.get("pulse", pulse)
            dash = frame.get("dash", dash)
        if tick > 0 and state == "playing":
            sim_tick += 1
            if wind_rng is not None:
                if sim_tick % 1800 == 0:
                    wind_direction = wind_rng.uniform(0, 360)
                wind = math.radians(wind_direction) if sim_tick >= 1800 and sim_tick % 1800 < 300 else None
            motes = [mote for mote in motes if mote["expires"] is None or mote["expires"] > sim_tick]
            drifters = [entry for entry in drifters if entry["state"] != "removed"
                        and (entry["state"] != "flee" or entry["expires"] > sim_tick)]
            move = frame.get("move", move)
            yaw = frame.get("cam_yaw_deg", yaw)
            next_dash = frame.get("dash", dash)
            charmed = sim_tick < charm_until
            if next_dash and not dash and sim_tick >= dash_until and (charmed or sim_tick >= dash_ready):
                dash_move, dash_yaw = (move if any(move) else [0, 1]), yaw
                length = math.hypot(*dash_move)
                dash_move = [axis / length for axis in dash_move]
                dash_until = sim_tick + round(tuning["dash_duration_s"] * TICKS_PER_SECOND)
                dash_ready = sim_tick if charmed else sim_tick + round(tuning["dash_cooldown_s"] * TICKS_PER_SECOND)
                write_record(output, type="event", tick=tick, name="dash", data={})
            dash = next_dash
            dashing = sim_tick < dash_until
            speed = tuning["dash_speed"] if dashing else CHARM_SPEED if charmed else tuning["player_speed"]
            next_jump = frame.get("jump", jump)
            previous_position = player["pos"].copy()
            vertical_speed, launch, fell = move_on_terrain(
                player, night, dash_move if dashing else move, dash_yaw if dashing else yaw,
                speed, next_jump and not jump, vertical_speed, launch, dashing, wind,
            )
            velocity = [0, 0, 0] if fell else [
                round((new - old) * TICKS_PER_SECOND, 3)
                for old, new in zip(previous_position, player["pos"])
            ]
            jump = next_jump
            if fell and player["flames"] > 0:
                player["flames"] -= 1
                hit_ready = sim_tick + math.ceil(tuning["invuln_s"] * TICKS_PER_SECOND)
                write_record(
                    output, type="event", tick=tick, name="player_hit",
                    data={"by": "fall", "flames": player["flames"], "dropped": 0, "lost": 0},
                )
            remaining = collect_motes(output, tick, player, motes, tuning)
            motes = remaining
            for charm in charms:
                if sim_tick >= charm["ready"] and ground_distance(player["pos"], charm["pos"]) <= tuning["pickup_radius"]:
                    charm_until = sim_tick + CHARM_DURATION
                    charm["ready"] = sim_tick + CHARM_RESPAWN
                    write_record(output, type="event", tick=tick, name="charm_picked",
                                 data={"charm_id": charm["id"], "charm_ticks": CHARM_DURATION})
            next_interact = frame.get("interact", interact)
            if next_interact and not interact:
                score += deposit_light(output, tick, player, lanterns, tuning)
            interact = next_interact

            next_pulse = frame.get("pulse", pulse)
            if next_pulse and not pulse and sim_tick >= pulse_ready and player["carried"] >= tuning["pulse_cost"]:
                score += pulse_shades(output, tick, sim_tick, player, shades, tuning)
                pulse_drifters(output, tick, sim_tick, player, drifters, motes, tuning["pulse_radius"])
                pulse_ready = sim_tick + math.ceil(tuning["pulse_cooldown_s"] * TICKS_PER_SECOND)
            pulse = next_pulse

            move_drifters(output, tick, sim_tick, player, drifters)
            contact = move_shades(sim_tick, shades, player["pos"], lanterns, tuning)
            if contact and sim_tick >= hit_ready and player["flames"] > 0:
                player["flames"] -= 1
                dropped = math.floor(player["carried"] * tuning["hit_drop_ratio"])
                player["carried"] -= dropped
                hit_ready = sim_tick + math.ceil(tuning["invuln_s"] * TICKS_PER_SECOND)
                write_record(
                    output, type="event", tick=tick, name="player_hit",
                    data={"by": "shade", "flames": player["flames"], "dropped": dropped},
                )
            spawn_shades(output, tick, sim_tick, night, player, shades, shade_rng)
            if replenish_motes and sim_tick % 120 == 0:
                occupied = {tuple(mote["pos"]) for mote in motes if mote["kind"] == "random"}
                for index, point in enumerate(MOTE_POINTS[night], start=1):
                    if point not in occupied:
                        motes.append({"id": f"M{index}-{sim_tick}", "pos": list(point),
                                      "kind": "random", "expires": None})
                        break
            if night > 1 and drifter_rng and sim_tick % 1200 == 0 and len(drifters) < 2:
                while True:
                    drifter_sequence += 1
                    drifter_id = f"D{drifter_sequence}"
                    if drifter_id not in used_drifter_ids:
                        break
                used_drifter_ids.add(drifter_id)
                drifters.append({"id": drifter_id, "pos": list(drifter_rng.choice(SHADE_POINTS[night])),
                                 "state": "idle", "stolen": 0, "expires": 0})

        time_left = max(0, duration - sim_tick / TICKS_PER_SECOND)
        reason = None
        if tick > 0 and state == "playing":
            if all(lantern["lit"] for lantern in lanterns):
                state, reason = "won", "all_lit"
                score += math.floor(time_left) * tuning["score"]["per_second_left"]
                score += player["flames"] * tuning["score"]["per_flame_left"]
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
                type="snapshot", tick=tick, sim_tick=sim_tick, night=night,
                wind={"active": wind is not None, "dir_deg": round(wind_direction, 3)},
                state=state, time_left_s=time_left, score=score, player={
                    **rounded_entity(player), "vel": velocity,
                    "grounded": vertical_speed == 0 and player["pos"][1] in ground_levels(night, player["pos"][0], player["pos"][2]),
                    "invuln": max(0, hit_ready - sim_tick - 1) > 0,
                    "dash_cd_s": max(0, dash_ready - sim_tick - 1) / TICKS_PER_SECOND,
                    "pulse_cd_s": max(0, pulse_ready - sim_tick - 1) / TICKS_PER_SECOND,
                    "charm_s": max(0, charm_until - sim_tick - (sim_tick == 0)) / TICKS_PER_SECOND,
                },
                lanterns=[rounded_entity(lantern) for lantern in lanterns],
                shades=[rounded_entity({key: shade[key] for key in ("id", "pos", "state")})
                        for shade in shades],
                motes_active=len(motes), motes=[
                    {**rounded_entity({key: mote[key] for key in ("id", "pos", "kind")}),
                     "ttl_s": None if mote["expires"] is None else (mote["expires"] - sim_tick) / TICKS_PER_SECOND}
                    for mote in motes
                ],
                drifters=[rounded_entity({key: entry[key] for key in ("id", "pos", "state", "stolen")})
                          for entry in drifters],
                charms=[{"id": charm["id"], "available": sim_tick >= charm["ready"],
                         "respawn_s": max(0, charm["ready"] - sim_tick) / TICKS_PER_SECOND}
                        for charm in charms],
            )
            write_record(output, **snapshot)
            if tick == 0:
                write_record(output, type="event", tick=0, name="night_start", data={"night": night})
            yield snapshot
        if state in ("won", "lost"):
            break
    write_record(output, type="end", ticks=tick, state=state, score=score)


def simulate(output, ticks, snapshot_every, tuning, frames, initial):
    for _ in simulation_steps(output, ticks, snapshot_every, tuning, frames, initial):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--night", required=True, type=int, choices=[1, 2, 3])
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
            initial = initial_state(scenario, args.seed, tuning, args.night)
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
