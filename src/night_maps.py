"""Map coordinates specified by Ticket-02."""

import math


def ring(radius, count, *, start=0, step=None, center_x=0, height=0):
    spacing = 360 / count if step is None else step
    points = []
    for index in range(count):
        angle = math.radians(start + index * spacing)
        points.append((center_x + radius * math.cos(angle), height, radius * math.sin(angle)))
    return points


LANTERNS = {
    1: [(0, 0, 25), (23.8, 0, 7.7), (14.7, 0, -20.2),
        (-14.7, 0, -20.2), (-23.8, 0, 7.7)],
    2: [(0, 0, 20), (17, 0, -10), (-17, 0, -10),
        (70, 0, 20), (87, 0, -10), (53, 0, -10)],
    3: [(0, 6, 6), (18, 3, 10), (-18, 3, 10), (35, 0, -10),
        (-35, 0, -10), (20, 0, -35), (-20, 0, -35)],
}

MOTE_POINTS = {
    1: ring(12, 8) + ring(33, 16),
    2: [point for center in (0, 70)
        for point in ring(10, 4, center_x=center) + ring(22, 8, center_x=center)],
    3: ring(34, 18) + ring(18, 8, start=20, step=20, height=3)
    + ring(5, 4, start=45, height=6),
}

SHADE_POINTS = {
    1: ring(37, 12, start=15, height=1),
    2: ring(26, 8, start=22.5, height=1) + ring(26, 8, start=22.5, center_x=70, height=1),
    3: ring(43, 16, height=1),
}

PADS = {
    1: [],
    2: [((20, 0, 18), (70, 0, 0), 14, 24), ((50, 0, -18), (0, 0, 0), 14, 24)],
    3: [((0, 3, 13), (0, 3, 0), 12, 8)],
}


def ground_levels(night, x, z):
    """Return the surfaces under a position, from lowest to highest."""
    radius = math.hypot(x, z)
    if night == 1:
        return [0] if radius <= 40 else []
    if night == 2:
        on_bridge = 26 <= x <= 44 and -2 <= z <= 2
        return [0] if radius <= 28 or math.hypot(x - 70, z) <= 28 or on_bridge else []
    if radius > 45:
        return []

    levels = [0]
    if z > 0 and 12 <= radius <= 24:
        levels.append(3)
    if radius <= 8:
        levels.append(6)
    for angle in (math.pi / 6, 5 * math.pi / 6):
        along = x * math.cos(angle) + z * math.sin(angle)
        across = -x * math.sin(angle) + z * math.cos(angle)
        if 24 <= along <= 30 and abs(across) <= 1.5:
            levels.append((30 - along) / 2)
    return sorted(set(levels))
