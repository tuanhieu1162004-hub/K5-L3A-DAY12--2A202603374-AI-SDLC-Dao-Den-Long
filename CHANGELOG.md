# Changelog

## Phase 3 · Contract v1.2

- Breaking: a night ends at dawn or when the player loses the last flame. `all_lit` is replaced by `dawn_survived` for a successful dawn.
- Breaking: lanterns consume fuel, can go out and can be refueled or relit. Initial lighting costs 10 motes and relighting costs 5.
- Breaking: deposits award 5 points per mote. Relights and draining Shades have distinct bonuses. Dawn awards fuel and flame points.
- Added fuel, lantern history and player capacity to snapshots, plus the `drain` Shade state and fuel events.

## Phase 2 · Contract v1.1

- Added three nights, pause, dash, Wind Charms, Drifters and Night 3 wind.

## Phase 1 · Contract v1.0

- Added the first playable island and fixed-step headless JSONL output.
