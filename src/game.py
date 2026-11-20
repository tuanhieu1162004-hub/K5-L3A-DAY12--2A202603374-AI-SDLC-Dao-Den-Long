"""Play Night 1 with a perspective camera and the headless simulation."""

import json
import math
import sys
import time
import tkinter as tk
from pathlib import Path

from headless import CONTRACT_PATH, ground_distance, initial_state, simulation_steps
from game_audio import GameAudio
from night_features import CHARM_POINTS
from night_maps import PADS


CONTROLS = "WASD: di chuyển    ← →: xoay camera    Space: nhảy    Shift: lướt    E: nạp đèn    Q: tỏa sáng    Esc/P: tạm dừng"
NIGHT_NAMES = ("Đảo Bến", "Cầu Tre", "Tháp Chuông")
SETTINGS_PATH = Path.home() / ".dao-den-long-settings.json"


def load_settings():
    defaults = {"volume": 70, "sensitivity": 100}
    try:
        saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        for name, maximum in (("volume", 100), ("sensitivity", 200)):
            if isinstance(saved, dict) and type(saved.get(name)) is int:
                defaults[name] = max(0 if name == "volume" else 25, min(maximum, saved[name]))
    except (OSError, ValueError):
        pass
    return defaults


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
        self.advance = tk.Button(root, text="Đêm kế tiếp", command=self.next_night)
        self.menu = tk.Button(root, text="Về menu", command=self.main_menu)
        self.start = tk.Button(root, text="Bắt đầu", command=self.begin_night)
        self.options = tk.Button(root, text="Cài đặt", command=self.open_settings)
        self.resume = tk.Button(root, text="Tiếp tục", command=self.request_resume)
        self.settings = load_settings()
        self.audio = GameAudio(root)
        self.settings_window = None
        self.keys = set()
        root.bind("<KeyPress>", lambda event: self.keys.add(event.keysym.lower()))
        root.bind("<KeyRelease>", lambda event: self.keys.discard(event.keysym.lower()))
        root.bind("<FocusOut>", lambda event: self.keys.clear())
        self.canvas.bind("<ButtonPress-1>", self.begin_camera_drag)
        self.canvas.bind("<B1-Motion>", self.drag_camera)
        self.tuning = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["tuning"]
        self.main_menu()
        self.update()

    def begin_camera_drag(self, event):
        self.drag_x = event.x

    def drag_camera(self, event):
        if self.screen == "game" and self.snapshot["state"] == "playing":
            self.yaw += (event.x - self.drag_x) * self.settings["sensitivity"] / 200
        self.drag_x = event.x

    def open_settings(self):
        if self.settings_window is not None:
            self.settings_window.lift()
            return
        dialog = self.settings_window = tk.Toplevel(self.root)
        dialog.title("Cài đặt")
        dialog.transient(self.root)
        volume = tk.IntVar(value=self.settings["volume"])
        sensitivity = tk.IntVar(value=self.settings["sensitivity"])
        tk.Scale(dialog, from_=0, to=100, orient="horizontal", label="Âm lượng", variable=volume).pack()
        tk.Scale(dialog, from_=25, to=200, orient="horizontal", label="Độ nhạy chuột", variable=sensitivity).pack()
        status = tk.Label(dialog)
        status.pack()

        def close():
            self.settings_window = None
            dialog.destroy()

        def save():
            values = {"volume": volume.get(), "sensitivity": sensitivity.get()}
            try:
                temporary = SETTINGS_PATH.with_suffix(".tmp")
                temporary.write_text(json.dumps(values), encoding="utf-8")
                temporary.replace(SETTINGS_PATH)
            except OSError:
                status.configure(text="Không lưu được cài đặt.")
                return
            self.settings = values
            close()

        tk.Button(dialog, text="Lưu", command=save).pack(pady=8)
        dialog.protocol("WM_DELETE_WINDOW", close)

    def main_menu(self):
        self.night, self.total_score = 1, 0
        self.reset()
        self.screen = "menu"
        self.start.configure(text="Bắt đầu")
        self.start.pack(pady=8)
        self.options.pack(pady=4)

    def begin_night(self):
        if self.screen == "menu":
            self.screen = "intro"
            self.start.configure(text="Vào Đêm")
        else:
            self.reset()

    def next_night(self):
        self.total_score += self.snapshot["score"]
        if self.night == 3:
            self.screen = "dawn"
            self.advance.pack_forget()
            return
        self.night += 1
        self.reset()
        self.screen = "intro"
        self.start.configure(text="Vào Đêm")
        self.start.pack(pady=8)

    def reset(self):
        for button in (self.restart, self.advance, self.menu, self.start, self.options, self.resume):
            button.pack_forget()
        self.screen = "game"
        self.keys.clear()
        self.yaw = 0
        self.tick = 0
        self.resume_input = None
        self.frames = {}
        self.steps = simulation_steps(
            self.on_record, sys.maxsize, 1,
            self.tuning, self.frames, initial_state({}, 42, self.tuning, self.night),
        )
        self.snapshot = next(self.steps)
        self.deadline = time.monotonic() + 1 / 60
        self.canvas.focus_set()

    def request_resume(self):
        self.resume_input = False

    def on_record(self, record):
        if record["type"] == "event":
            name = record["name"]
            cue = record["data"]["result"] if name == "game_over" else name
            self.audio.play(cue, self.settings["volume"])

    def update(self):
        now = time.monotonic()
        self.deadline = max(self.deadline, now - 0.1)
        while self.screen == "game" and self.snapshot["state"] in ("playing", "paused") and self.deadline <= now:
            if self.snapshot["state"] == "playing":
                self.yaw += 2 * (("right" in self.keys) - ("left" in self.keys))
            self.frames.clear()
            pause = bool(self.keys & {"escape", "p"})
            if self.resume_input is not None:
                pause = self.resume_input
                self.resume_input = True if not pause else None
            self.frames[self.tick] = {
                "move": [("d" in self.keys) - ("a" in self.keys), ("w" in self.keys) - ("s" in self.keys)],
                "cam_yaw_deg": self.yaw, "jump": "space" in self.keys,
                "interact": "e" in self.keys, "pulse": "q" in self.keys,
                "pause": pause,
                "dash": bool(self.keys & {"shift_l", "shift_r"}),
            }
            previous = self.snapshot
            self.snapshot = next(self.steps)
            if self.snapshot["sim_tick"] != previous["sim_tick"] and self.snapshot["state"] == "playing":
                current_time = math.ceil(self.snapshot["time_left_s"])
                if current_time <= 10 and current_time != math.ceil(previous["time_left_s"]):
                    self.audio.play("countdown", self.settings["volume"])
                elif previous["player"]["grounded"] and self.snapshot["player"]["vel"][1] > 0 and "space" in self.keys:
                    self.audio.play("jump", self.settings["volume"])
                elif self.night == 3 and self.snapshot["sim_tick"] % 1800 == 1680:
                    self.audio.play("wind", self.settings["volume"])
                elif self.snapshot["sim_tick"] % 360 == 1:
                    self.audio.play("ambient", self.settings["volume"])
            self.tick += 1
            self.deadline += 1 / 60
        self.draw()
        self.root.after(10, self.update)

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

        def camera_space(point):
            x, y, z = point
            dx, dy, dz = x - px, y - 7 - py * 0.35, z - pz
            forward = dx * sine + dz * cosine + 11
            return dx * cosine - dz * sine, forward * 0.447 + dy * 0.894, forward * 0.894 - dy * 0.447

        def perspective(point):
            right, up, depth = point
            return width / 2 + right * focal / depth, height / 2 - up * focal / depth, depth

        def project(point):
            camera_point = camera_space(point)
            return perspective(camera_point) if camera_point[2] >= 0.5 else None

        def polygon(points, color):
            vertices = [camera_space(point) for point in points]
            clipped = []
            previous = vertices[-1]
            for current in vertices:
                previous_visible = previous[2] >= 0.5
                current_visible = current[2] >= 0.5
                if previous_visible != current_visible:
                    fraction = (0.5 - previous[2]) / (current[2] - previous[2])
                    clipped.append(tuple(a + fraction * (b - a) for a, b in zip(previous, current)))
                if current_visible:
                    clipped.append(current)
                previous = current
            if len(clipped) >= 3:
                screen = [perspective(point) for point in clipped]
                canvas.create_polygon([coordinate for x, y, _ in screen for coordinate in (x, y)], fill=color)

        def disc(point, radius, color):
            screen = project(point)
            if screen is not None:
                x, y, depth = screen
                size = radius * focal / depth
                canvas.create_oval(x - size, y - size, x + size, y + size, fill=color, outline="")

        lit = sum(lantern["lit"] for lantern in state["lanterns"])
        canvas.configure(background="#17162d")
        for band in range(7):
            top = height * band / 7
            canvas.create_rectangle(0, top, width, height * (band + 1) / 7,
                                    fill=f"#{23+band*4:02x}{22+band*4:02x}{45+band*6:02x}", outline="")
        for index in range(28):
            x = (index * 0.618034 + self.yaw / 720) % 1 * width
            y = (0.04 + (index * 0.381966 % 1) * 0.45) * height
            size = 2 if index % 6 == 0 else 1
            canvas.create_oval(x-size, y-size, x+size, y+size,
                               fill="#d8cce5" if size == 2 else "#9d92ba", outline="")
        moon = min(width, height) * .055
        mx, my = width * .79, height * .17
        for scale, color in ((1.45, "#37304d"), (1.2, "#52435b"), (1, "#fff0bd")):
            radius = moon * scale
            canvas.create_oval(mx-radius, my-radius, mx+radius, my+radius, fill=color, outline="")
        for index in range(5):
            y = height * (.58 + .072 * index)
            canvas.create_oval(-width*.13 + index*width*.06, y, width*(.87+index*.13), y+height*.15,
                               fill=("#34324f", "#3d3855", "#47405d", "#535069", "#5d566e")[index], outline="")
        ground = f"#{36+lit*10:02x}{48+lit*9:02x}{55+lit*3:02x}"

        def surface(center, radius, y, color, arc=math.tau, inner=0, depth=0):
            if depth:
                sides = []
                for index in range(20):
                    a, b = index * arc / 20, (index+1) * arc / 20
                    ax, az = center + radius*math.cos(a), radius*math.sin(a)
                    bx, bz = center + radius*math.cos(b), radius*math.sin(b)
                    points = [(ax,y,az),(bx,y,bz),(bx,y-depth,bz),(ax,y-depth,az)]
                    sides.append((camera_space(((ax+bx)/2,y,(az+bz)/2))[2], points,
                                  ("#302c45", "#43394f", "#3a334b")[index % 3]))
                for _, points, side_color in sorted(sides, reverse=True):
                    polygon(points, side_color)
            if not inner and arc == math.tau:
                polygon([(center + radius*math.cos(index*arc/40), y,
                          radius*math.sin(index*arc/40)) for index in range(40)], color)
                return
            for index in range(24):
                a, b = index * arc / 24, (index + 1) * arc / 24
                polygon([(center+size*math.cos(theta), y, size*math.sin(theta))
                         for size, theta in ((inner,a),(radius,a),(radius,b),(inner,b))], color)

        surface(0, {1: 40, 2: 28, 3: 45}[self.night], 0, ground, depth=5)
        if self.night == 2:
            surface(70, 28, 0, ground, depth=5)
            for index in range(15):
                x = 26 + index * 1.2
                polygon([(x,0,-2),(x+1.1,0,-2),(x+1.1,0,2),(x,0,2)],
                        ("#92704e", "#a48159")[index % 2])
        elif self.night == 3:
            surface(0, 24, 3, "#506458", math.pi, 12)
            surface(0, 8, 6, "#616f62", depth=6)
            for bearing in (math.pi / 6, 5 * math.pi / 6):
                sine_b, cosine_b = math.sin(bearing), math.cos(bearing)
                polygon([(radius*cosine_b-offset*sine_b, y, radius*sine_b+offset*cosine_b)
                         for radius, offset, y in ((30,-1.5,0),(24,-1.5,3),(24,1.5,3),(30,1.5,0))],
                        "#7e7460")
            disc((0, 10, 0), 2, "#675461")
        for point, _, _, _ in PADS[self.night]:
            disc(point, .85, "#70b4a5")
        for point, charm in zip(CHARM_POINTS[self.night], state["charms"]):
            if charm["available"]:
                disc((point[0], point[1] + .45, point[2]), .28, "#da5a4d")

        entities = [(entity["pos"], kind, entity)
                    for kind, key in (("mote", "motes"), ("shade", "shades"), ("lantern", "lanterns"), ("drifter", "drifters"))
                    for entity in state[key]]
        entities.append((player["pos"], "player", player))
        entities.sort(key=lambda item: (item[0][0]-px)*sine + (item[0][2]-pz)*cosine, reverse=True)
        for (x, y, z), kind, entity in entities:
            if kind == "mote":
                disc((x, y + .4, z), .14, "#ffdc72")
            elif kind == "shade":
                disc((x, y, z), .56, "#9470ca" if entity["state"] == "stunned" else "#392347")
            elif kind == "drifter":
                disc((x, y, z), .48, "#799b9c")
            elif kind == "lantern":
                base, top = project((x, y, z)), project((x, y + 2, z))
                if base and top:
                    canvas.create_line(*base[:2], *top[:2], width=max(2, 0.14 * focal / top[2]), fill="#7f563e")
                if entity["lit"]:
                    disc((x, y + 2, z), .85, "#9e672e")
                for offset, shade in ((-.24, "#a45136"), (.24, "#d08047")):
                    polygon([(x+(offset-.25)*cosine,y+1.64,z-(offset-.25)*sine),
                             (x+(offset+.25)*cosine,y+1.64,z-(offset+.25)*sine),
                             (x+(offset+.25)*cosine,y+2.32,z-(offset+.25)*sine),
                             (x+(offset-.25)*cosine,y+2.32,z-(offset-.25)*sine)],
                            shade if entity["lit"] else "#60475e")
                disc((x, y + 2, z), .22, "#ffe1a0" if entity["lit"] else "#816780")
                for cap in (1.61, 2.33):
                    disc((x, y + cap, z), .09, "#e2a96b")
            else:
                disc((x, y + .55, z), .37, "#62b6b0")
                disc((x, y + 1.12, z), .25, "#ffe2ad")
                hat = []
                for index in range(10):
                    a, b = index*math.tau/10, (index+1)*math.tau/10
                    points = [(x,y+1.65,z), (x+.49*math.cos(a),y+1.3,z+.49*math.sin(a)),
                              (x+.49*math.cos(b),y+1.3,z+.49*math.sin(b))]
                    hat.append((sum(camera_space(point)[2] for point in points), points,
                                ("#d9ac58", "#f0cb79", "#bf914d")[index%3]))
                for _, points, color in sorted(hat, reverse=True):
                    polygon(points, color)
                disc((x + cosine * .4, y + 1.1, z - sine * .4), .12, "#ffcf64")
        minutes, seconds = divmod(math.ceil(state["time_left_s"]), 60)
        light = "■" * min(10, player["carried"]) + "□" * max(0, 10 - player["carried"])
        self.hud.configure(text=f"Ngọn Lửa {player['flames']}   •   {minutes:02}:{seconds:02}   •   Đèn {lit}/{len(state['lanterns'])}   •   Điểm {state['score']}\n{light}   •   Lướt {player['dash_cd_s']:.1f}s   •   Pulse {player['pulse_cd_s']:.1f}s")
        if self.screen == "game" and state["state"] == "playing":
            if state["time_left_s"] <= 30 and state["sim_tick"] // 20 % 2 == 0:
                canvas.create_text(width/2, 22, text=f"{minutes:02}:{seconds:02}", fill="#ff535a",
                                   font=("TkDefaultFont", 18, "bold"))
            candidates = [lantern for lantern in state["lanterns"] if not lantern["lit"]]
            if candidates:
                nearest = min(candidates, key=lambda lantern: ground_distance(player["pos"], lantern["pos"]))
                distance = ground_distance(player["pos"], nearest["pos"])
                if distance <= self.tuning["interact_radius"]:
                    canvas.create_text(width/2, height-25,
                                       text=f"E — Nạp ánh sáng ({nearest['deposited']}/{self.tuning['lantern_cost']})",
                                       fill="#ffe1a4")
                else:
                    screen = project(nearest["pos"])
                    if screen is None or not (0 <= screen[0] <= width and 0 <= screen[1] <= height):
                        dx, _, dz = (b-a for a, b in zip(player["pos"], nearest["pos"]))
                        bearing = math.atan2(dx, dz) - angle
                        cx, cy = width/2, height-42
                        canvas.create_line(cx, cy, cx+25*math.sin(bearing), cy-25*math.cos(bearing),
                                           arrow="last", fill="#ffe1a4", width=3)
            if self.night == 3 and state["sim_tick"] % 1800 >= 1680:
                canvas.create_text(width/2, 48, text="Gió mạnh sắp đến", fill="#b8e2dd")
                for index in range(10):
                    x = (index * width / 10 + state["sim_tick"] * 4) % width
                    y = height * (0.18 + index % 5 * 0.12)
                    canvas.create_polygon(x, y, x+13, y-5, x+8, y+4, fill="#9fb882")
        if self.screen != "game":
            messages = {
                "menu": "Đảo Đèn Lồng",
                "intro": f"Đêm {self.night} · {NIGHT_NAMES[self.night - 1]}\nÔng Đăng: Hãy thắp sáng những chiếc đèn trên đảo.",
                "dawn": f"Bình Minh\nTổng điểm {self.total_score}",
            }
            canvas.create_text(width/2, height/3, text=messages[self.screen],
                               justify="center", fill="#ffe1a4", font=("TkDefaultFont", 24, "bold"))
        elif state["state"] == "paused":
            canvas.create_text(width/2, height/3, text="Tạm dừng · Esc/P để tiếp tục",
                               fill="#ffe1a4", font=("TkDefaultFont", 24, "bold"))
            if not self.menu.winfo_manager():
                self.resume.pack(pady=4)
                self.restart.pack(pady=4)
                self.menu.pack(pady=4)
                self.options.pack(pady=4)
        elif state["state"] in ("won", "lost"):
            canvas.create_text(width/2, height/3, text="Đảo đã sáng!" if state["state"] == "won" else "Đêm đã kết thúc",
                               fill="#ffe1a4", font=("TkDefaultFont", 28, "bold"))
            button = self.advance if state["state"] == "won" else self.restart
            if not button.winfo_manager():
                button.pack(pady=4)
                self.menu.pack(pady=4)
        else:
            self.restart.pack_forget()
            self.menu.pack_forget()
            self.options.pack_forget()
            self.resume.pack_forget()


if __name__ == "__main__":
    window = tk.Tk()
    Game(window)
    window.mainloop()
