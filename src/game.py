"""Play Night 1 with a perspective camera and the headless simulation."""

import json
import math
import time
import tkinter as tk

from headless import CONTRACT_PATH, initial_state, simulation_steps


RADIUS = 16
CONTROLS = "WASD: di chuyển    ← →: xoay camera    Space: nhảy    E: nạp đèn    Q: tỏa sáng"


class Game:
    def __init__(self, root):
        self.root = root
        root.title("Đảo Đèn Lồng • Đêm 1 – Đảo Bến")
        self.canvas = tk.Canvas(root, width=920, height=620, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.hud = tk.Label(root, font=("TkDefaultFont", 13))
        self.hud.pack(pady=6)
        tk.Label(root, text=CONTROLS).pack(pady=4)
        self.restart = tk.Button(root, text="Chơi lại", command=self.reset)
        self.keys = set()
        root.bind("<KeyPress>", lambda event: self.keys.add(event.keysym.lower()))
        root.bind("<KeyRelease>", lambda event: self.keys.discard(event.keysym.lower()))
        root.bind("<FocusOut>", lambda event: self.keys.clear())
        self.tuning = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["tuning"]
        self.reset()
        self.update()

    def reset(self):
        self.restart.pack_forget()
        self.keys.clear()
        self.yaw = 0
        self.tick = 0
        self.frames = {}
        self.steps = simulation_steps(
            None, math.ceil(self.tuning["night1_duration_s"] * 60), 1,
            self.tuning, self.frames, initial_state({}, 42, self.tuning), RADIUS,
        )
        self.snapshot = next(self.steps)
        self.deadline = time.monotonic() + 1 / 60
        self.canvas.focus_set()

    def update(self):
        now = time.monotonic()
        self.deadline = max(self.deadline, now - 0.1)
        while self.snapshot["state"] == "playing" and self.deadline <= now:
            self.yaw += 2 * (("right" in self.keys) - ("left" in self.keys))
            self.frames.clear()
            self.frames[self.tick] = {
                "move": [("d" in self.keys) - ("a" in self.keys), ("w" in self.keys) - ("s" in self.keys)],
                "cam_yaw_deg": self.yaw, "jump": "space" in self.keys,
                "interact": "e" in self.keys, "pulse": "q" in self.keys,
            }
            self.snapshot = next(self.steps)
            self.tick += 1
            self.deadline += 1 / 60
        self.draw()
        self.root.after(16, self.update)

    def draw(self):
        canvas = self.canvas
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        state = self.snapshot
        player = state["player"]
        px, py, pz = player["pos"]
        angle = math.radians(self.yaw)
        sine, cosine = math.sin(angle), math.cos(angle)
        focal = min(width, height) * 0.95

        def project(point):
            x, y, z = point
            dx, dy, dz = x - px, y - 7 - py * 0.35, z - pz
            forward = dx * sine + dz * cosine + 11
            depth = forward * 0.894 - dy * 0.447
            if depth <= 0.2:
                return None
            right = dx * cosine - dz * sine
            up = forward * 0.447 + dy * 0.894
            return width / 2 + right * focal / depth, height / 2 - up * focal / depth, depth

        def polygon(points, color):
            screen = [project(point) for point in points]
            if all(point is not None for point in screen):
                canvas.create_polygon([coordinate for x, y, _ in screen for coordinate in (x, y)], fill=color)

        def disc(point, radius, color):
            screen = project(point)
            if screen is not None:
                x, y, depth = screen
                size = radius * focal / depth
                canvas.create_oval(x - size, y - size, x + size, y + size, fill=color, outline="")

        lit = sum(lantern["lit"] for lantern in state["lanterns"])
        canvas.configure(background="#17152c")
        canvas.create_oval(width * .76, height * .07, width * .84, height * .19, fill="#fff0bd", outline="")
        rim = [(RADIUS * math.cos(i * math.tau / 64), 0, RADIUS * math.sin(i * math.tau / 64)) for i in range(64)]
        ground = f"#{36+lit*10:02x}{48+lit*9:02x}{55+lit*3:02x}"
        for i, point in enumerate(rim):
            polygon([(0, 0, 0), point, rim[(i + 1) % len(rim)]], ground)

        entities = [(entity["pos"], kind, entity)
                    for kind, key in (("mote", "motes"), ("shade", "shades"), ("lantern", "lanterns"))
                    for entity in state[key]]
        entities.append((player["pos"], "player", player))
        entities.sort(key=lambda item: (item[0][0]-px)*sine + (item[0][2]-pz)*cosine, reverse=True)
        for (x, y, z), kind, entity in entities:
            if kind == "mote":
                disc((x, y + .4, z), .14, "#ffdc72")
            elif kind == "shade":
                disc((x, y, z), .56, "#9470ca" if entity["state"] == "stunned" else "#392347")
            elif kind == "lantern":
                base, top = project((x, y, z)), project((x, y + 2, z))
                if base and top:
                    canvas.create_line(*base[:2], *top[:2], width=max(2, 0.14 * focal / top[2]), fill="#7f563e")
                if entity["lit"]:
                    disc((x, y + 2, z), .85, "#9e672e")
                disc((x, y + 2, z), .46, "#ffcb6c" if entity["lit"] else "#6e5267")
            else:
                disc((x, y + .55, z), .37, "#62b6b0")
                disc((x, y + 1.12, z), .25, "#ffe2ad")
                center = project((x, y + 1.4, z))
                if center:
                    sx, sy, depth = center
                    size = focal / depth
                    canvas.create_polygon(sx, sy-.25*size, sx-.48*size, sy+.1*size,
                                          sx+.48*size, sy+.1*size, fill="#d9ac58")
                    disc((x + cosine * .4, y + 1.1, z - sine * .4), .12, "#ffcf64")
        self.hud.configure(text=f"Máu {player['flames']}   •   Ánh sáng {player['carried']}/{self.tuning['carry_capacity']}   •   Đèn {lit}/5   •   {math.ceil(state['time_left_s'])} giây   •   Điểm {state['score']}")
        if state["state"] != "playing":
            canvas.create_text(width/2, height/3, text="Đảo đã sáng!" if state["state"] == "won" else "Đêm đã kết thúc",
                               fill="#ffe1a4", font=("TkDefaultFont", 28, "bold"))
            if not self.restart.winfo_manager():
                self.restart.pack(pady=8)


if __name__ == "__main__":
    window = tk.Tk()
    Game(window)
    window.mainloop()
