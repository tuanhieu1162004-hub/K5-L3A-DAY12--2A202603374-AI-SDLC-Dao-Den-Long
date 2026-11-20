"""Panda3D frontend for the shared simulation."""

import argparse
import json
import math
import random
import sys
import tempfile
from pathlib import Path

from direct.gui.DirectGui import DirectButton, DirectEntry, DirectSlider
from direct.gui.OnscreenText import OnscreenText
from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    AmbientLight, CardMaker, ClockObject, DirectionalLight, Filename, Fog, MouseButton,
    PointLight, WindowProperties,
)

from headless import CONTRACT_PATH, ground_distance, initial_state, simulation_steps
import control_settings
from game_audio import TONES, write_wave
from leaderboard import export_scores, record_score, scores
from night_features import CHARM_POINTS
from night_maps import PADS
from panda_scene import island, keeper, landscape, lantern, model, place

PALETTE_PATH = Path.home() / ".dao-den-long-palette.json"


class LanternIsland(ShowBase):
    def __init__(self, benchmark=False):
        super().__init__()
        self.benchmark = benchmark
        self.disableMouse()
        if self.win:
            properties = WindowProperties()
            properties.setTitle("Đảo Đèn Lồng • Panda3D")
            properties.setSize(1280, 720)
            self.win.requestProperties(properties)
        self.setBackgroundColor(.065, .056, .13)
        self.camLens.setFov(75)
        self.camLens.setNearFar(.15, 180)
        self.fog = Fog("night mist")
        self.fog.setColor(.065, .056, .13)
        self.fog.setLinearRange(24, 88)
        self.render.setFog(self.fog)
        self.ambient = AmbientLight("island glow")
        self.render.setLight(self.render.attachNewNode(self.ambient))
        moon = DirectionalLight("moonlight")
        moon.setColor((.65, .68, .98, 1))
        moon_node = self.render.attachNewNode(moon)
        moon_node.setHpr(35, -55, 0)
        self.render.setLight(moon_node)
        glow = PointLight("warm lantern glow")
        glow.setColor((1, .53, .20, 1))
        glow.setAttenuation((1, .12, .055))
        self.lantern_glow = self.render.attachNewNode(glow)
        sky = self.render.attachNewNode("night sky")
        sky.setLightOff()
        sky.setFogOff()
        moon_mesh = model(sky, "moon", [(0,-3),(2.5,-1.6),(3,0),(2.5,1.6),(0,3)], [(1,.85,.61)], 16)
        moon_mesh.setPos(34, 78, 35)
        rng = random.Random(912)
        for _ in range(44):
            bearing = rng.uniform(0, math.tau)
            point = model(sky,"star",[(0,-.14),(.19,0),(0,.14)],[(.75,.76,.96)],4)
            point.setPos(105*math.cos(bearing),105*math.sin(bearing),rng.uniform(13,65))
        self.keys = set()
        (self.bindings, self.large_text, self.reduce_motion,
         self.volume, self.sensitivity) = control_settings.load()
        self.sounds = {}
        self.sound_dir = None
        self.mouse_x = None
        self.accept("mouse3-up", self.stop_drag)
        for key in control_settings.KEYS | {"arrow_left", "arrow_right"}:
            self.accept(key, self.keys.add, [key])
            self.accept(f"{key}-up", self.keys.discard, [key])
        self.accept("enter", self.continue_game)
        self.accept("r", self.restart_night)
        self.accept("m", self.main_menu)
        self.accept("l", self.show_leaderboard)
        self.accept("f1", self.toggle_controls)
        self.accept("f2", self.toggle_palette)
        try:
            self.easy_palette = json.loads(PALETTE_PATH.read_text(encoding="utf-8")) is True
        except (OSError, ValueError):
            self.easy_palette = False
        self.tuning = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["tuning"]
        self.hud = OnscreenText(text="", pos=(0, .87), scale=.047, fg=(1,.90,.71,1), mayChange=True)
        self.prompt = OnscreenText(text="", pos=(0, -.74), scale=.044, fg=(1,.85,.53,1), mayChange=True)
        self.help = OnscreenText(text="F1: settings  |  F2: palette  |  Left/Right: camera",
                                 pos=(0, -.94), scale=.043, fg=(.83,.80,.92,1))
        self.direction = OnscreenText(text=">", scale=.10, fg=(1,.76,.43,1))
        self.direction.hide()
        self.title = OnscreenText(text="", pos=(0, .16), scale=.095, fg=(1,.78,.43,1), mayChange=True)
        self.button = DirectButton(text="Play", scale=.072, pos=(0,0,-.21), command=self.continue_game,
                                   frameSize=(-3.9, 3.9, -.48, .80),
                                   frameColor=(.96,.71,.35,1), text_fg=(.12,.09,.15,1))
        self.score_entry = DirectEntry(initialText="", scale=.055, width=12, pos=(-.34,0,-.39),
                                       command=self.save_score, focus=0)
        self.score_entry.hide()
        self.score_button = DirectButton(text="Save score", scale=.047, pos=(0,0,-.53),
                                         command=self.save_score)
        self.score_button.hide()
        self.score_status = OnscreenText(text="", pos=(0,-.65), scale=.044, mayChange=True)
        self.score_board = OnscreenText(text="", pos=(0,.48), scale=.056, fg=(1,.90,.71,1), mayChange=True)
        self.controls_text = OnscreenText(text="", pos=(0,.56), scale=.054, fg=(1,.90,.71,1), mayChange=True)
        self.controls_entry = DirectEntry(scale=.055, width=28, pos=(-.75,0,.12), command=self.save_bindings)
        self.volume_slider = DirectSlider(range=(0,100), value=self.volume, scale=.31, pos=(-.48,0,-.5))
        self.sensitivity_slider = DirectSlider(range=(25,200), value=self.sensitivity, scale=.31, pos=(.48,0,-.5))
        self.slider_label = OnscreenText(text="Volume                                  Mouse sensitivity",
                                         pos=(0,-.43), scale=.052)
        self.controls_buttons = [
            DirectButton(text=label, scale=.054, pos=(x,0,y), command=callback)
            for label,x,y,callback in (
                ("Save",-.55,-.10,self.save_bindings), ("Defaults",-.12,-.10,self.default_bindings),
                ("Back",.34,-.10,self.toggle_controls), ("Larger text",-.32,-.28,self.toggle_text),
                ("Reduce motion",.37,-.28,self.toggle_motion),
            )
        ]
        for widget in self.controls_widgets():
            widget.hide()
        self.apply_text_scale()
        self.world = None
        self.main_menu()
        self.taskMgr.add(self.update_game, "game loop")

    def toggle_controls(self):
        if self.screen == "controls":
            self.controls_entry["focus"] = 0
            self.screen = self.controls_return
        elif self.screen == "menu" or self.snapshot["state"] == "paused":
            self.controls_return = self.screen
            self.screen = "controls"
            self.controls_entry.enterText(" ".join(self.bindings.values()))
            self.controls_message = ""
        self.keys.clear()

    def controls_widgets(self):
        return (self.controls_entry, *self.controls_buttons, self.volume_slider,
                self.sensitivity_slider, self.slider_label)

    def stop_drag(self):
        self.mouse_x = None

    def play_sound(self, cue):
        if self.benchmark or not self.volume or cue not in TONES:
            return
        if cue not in self.sounds:
            if self.sound_dir is None:
                self.sound_dir = tempfile.TemporaryDirectory()
            path = Path(self.sound_dir.name) / f"{cue}.wav"
            write_wave(path, cue, 100)
            self.sounds[cue] = self.loader.loadSfx(Filename.fromOsSpecific(str(path)))
        sound = self.sounds[cue]
        sound.setVolume(self.volume / 100)
        sound.setLoop(cue == "ambient")
        sound.play()

    def on_record(self, record):
        if record["type"] == "event":
            cue = record["data"]["result"] if record["name"] == "game_over" else record["name"]
            self.play_sound(cue)

    def persist_settings(self, bindings):
        volume = round(self.volume_slider["value"])
        sensitivity = round(self.sensitivity_slider["value"])
        control_settings.save(bindings, self.large_text, self.reduce_motion, volume, sensitivity)
        self.volume, self.sensitivity = volume, sensitivity
        if "ambient" in self.sounds:
            self.sounds["ambient"].setVolume(volume / 100)

    def save_bindings(self, text=None):
        try:
            bindings = control_settings.parse(self.controls_entry.get() if text is None else text)
            self.persist_settings(bindings)
            self.bindings = bindings
            self.controls_message = "Saved"
        except (ValueError, OSError) as error:
            self.controls_message = str(error)

    def default_bindings(self):
        self.controls_entry.enterText(" ".join(control_settings.DEFAULT.values()))
        self.save_bindings()

    def apply_text_scale(self):
        scale = 1.25 if self.large_text else 1
        for widget, normal in ((self.hud,.052),(self.prompt,.052),(self.help,.052),
                               (self.title,.095),(self.score_board,.056),(self.controls_text,.054)):
            widget.setScale(scale * normal)

    def toggle_text(self):
        self.large_text = not self.large_text
        self.apply_text_scale()
        self.persist_display()

    def toggle_motion(self):
        self.reduce_motion = not self.reduce_motion
        self.persist_display()

    def persist_display(self):
        try:
            self.persist_settings(self.bindings)
            self.controls_message = "Saved"
        except OSError as error:
            self.controls_message = str(error)

    def toggle_palette(self):
        self.easy_palette = not self.easy_palette
        try:
            PALETTE_PATH.write_text(json.dumps(self.easy_palette), encoding="utf-8")
        except OSError:
            pass

    def main_menu(self):
        if "ambient" in self.sounds:
            self.sounds["ambient"].stop()
        self.night = 1
        self.total_score = 0
        self.restart_night()
        self.screen = "menu"

    def show_leaderboard(self):
        if self.screen == "menu":
            self.leaderboard_entries = scores()
            self.screen = "scores"

    def save_score(self, name=None):
        if self.saved_score or not (self.screen == "dawn" or self.snapshot["state"] == "lost"):
            return
        try:
            record_score(self.score_entry.get() if name is None else name,
                         self.total_score, 3 if self.screen == "dawn" else self.night - 1, 42)
        except (OSError, ValueError) as error:
            self.score_status.setText(str(error))
            return
        self.saved_score = True
        self.score_status.setText("Score saved")

    def restart_night(self):
        self.keys.clear()
        self.frames = {}
        self.yaw = 0
        self.accumulator = 0
        self.spawn_hint_until = 0
        self.spawn_hint_pos = None
        self.steps = simulation_steps(self.on_record, sys.maxsize, 1, self.tuning, self.frames,
                                      initial_state({}, 42, self.tuning, self.night))
        self.snapshot = next(self.steps)
        self.screen = "game"
        self.saved_score = False
        self.score_entry.enterText("")
        self.score_status.setText("")
        if self.world is not None:
            self.world.removeNode()
        self.world = self.render.attachNewNode("night")
        island(self.world, {1:40, 2:28, 3:45}[self.night])
        if self.night == 2:
            island(self.world, 28, 70)
            for index in range(18):
                plank = model(self.world, "bamboo", [(0,-.18),(1,-.18),(1,0),(0,0)],
                              [(.43,.26,.16),(.69,.49,.28)], 4)
                plank.setScale(.55, 2.1, 1)
                plank.setPos(26.5 + index, 0, 0)
        elif self.night == 3:
            for sign in (-1, 1):
                ramp = model(self.world, "ramp", [(0,-.13),(1,-.13),(1,0),(0,0)], [(.54,.39,.27)], 4)
                ramp.setScale(3.5, 1.8, 1)
                ramp.setPos(sign*23.38, 13.5, 1.45)
                ramp.setHpr(30 if sign > 0 else 150, 0, 27 if sign > 0 else -27)
            platform = model(self.world, "upper terrace", [(0,0),(8,0),(8,6),(0,6)], [(.25,.34,.34)], 28)
            model(platform,"bell tower",[(2,6),(2,13),(2.5,13.2),(0,14)],[(.46,.34,.30),(.73,.42,.30)], 12)
            for degree in range(5, 180, 10):
                angle = math.radians(degree)
                tile = model(self.world, "terrace", [(0,0),(6.3,0),(6.3,3),(0,3)], [(.30,.45,.36)], 12)
                tile.setPos(18*math.cos(angle),18*math.sin(angle),0)
        for position, _, _, _ in PADS[self.night]:
            node = model(self.world, "jump pad", [(0,0),(.95,0),(1,.13),(0,.16)], [(.35,.84,.69)])
            place(node, position)
        if not self.benchmark:
            landscape(self.world, self.night, [entry["pos"] for entry in self.snapshot["lanterns"]])
        self.player = keeper(self.world)
        self.lanterns = {}
        for state in self.snapshot["lanterns"]:
            node, paper = lantern(self.world)
            place(node, state["pos"])
            card = CardMaker("fuel gauge")
            card.setFrame(0, 1, 0, .14)
            meter = node.attachNewNode(card.generate())
            meter.setPos(-.5, 0, 3)
            meter.setBillboardPointEye()
            meter.setLightOff()
            meter.setTwoSided(True)
            tear = model(node,"torn paper",[(0,1.91),(.13,2.03),(.14,2.22),(0,2.36)],[(.11,.08,.17)],4)
            tear.setY(-.56)
            self.lanterns[state["id"]] = (paper, meter, tear)
        self.charm_nodes = []
        for position in CHARM_POINTS[self.night]:
            node = model(self.world,"wind charm",[(0,.35),(.24,.40),(.31,.73),(0,1.05)],[(.91,.22,.29),(.99,.59,.24)],5)
            place(node, position)
            self.charm_nodes.append(node)
        self.entities = {}

    def continue_game(self):
        if self.screen == "menu":
            self.screen = "intro"
        elif self.screen == "intro":
            self.restart_night()
            self.play_sound("ambient")
        elif self.snapshot["state"] == "won" and self.screen == "game":
            self.total_score += self.snapshot["score"]
            if self.night == 3:
                self.screen = "dawn"
            else:
                self.night += 1
                self.restart_night()
                self.screen = "intro"
        elif self.snapshot["state"] == "lost":
            self.restart_night()
        elif self.screen in ("scores", "dawn"):
            self.main_menu()

    def draw_entities(self, state):
        active = set()
        for kind, data in (("mote", state["motes"]), ("shade", state["shades"]), ("drifter", state["drifters"])):
            for entity in data:
                key = (kind, entity["id"])
                active.add(key)
                if key not in self.entities:
                    if kind == "mote":
                        node = model(self.world,kind,[(0,.28),(.23,.49),(0,.70)],[(1,.81,.32)],6)
                        node.setLightOff()
                    elif kind == "shade":
                        node = model(self.world,kind,[(0,-.8),(.44,-.58),(.66,.14),(.33,.65),(0,.83)],
                                     [(.25,.13,.34),(.33,.17,.43),(.19,.11,.30)],8)
                        accent = model(node,"accent",[(0,-.26),(.65,-.09),(.68,.02),(0,.12)],[(1,1,1)],8)
                        accent.setLightOff()
                        for x in (-.21,.21):
                            eye = model(accent,"eye",[(0,.16),(.09,.24),(0,.34)],[(1,1,1)],8)
                            eye.setPos(x,-.61,0)
                        accent.flattenStrong()
                    else:
                        node = model(self.world,kind,[(0,-.12),(.43,.03),(.29,.19),(0,.28)],[(.48,.77,.79)],6)
                    self.entities[key] = node
                node = self.entities[key]
                place(node, entity["pos"])
                if kind == "mote":
                    node.setZ(node.getZ() + .13*math.sin(state["sim_tick"]*.1 + node.getX()))
                elif kind == "shade":
                    color_state = (entity["state"] == "stunned", self.easy_palette)
                    if node.getPythonTag("color_state") != color_state:
                        node.setPythonTag("color_state", color_state)
                        node.setColorScale(1.45,1.45,1.65,1) if color_state[0] else node.clearColorScale()
                        node.find("accent").setColor((0,.702,1,1) if self.easy_palette else (.478,.235,1,1))
                    node.lookAt(self.camera)
                    node.setP(0)
        for key in self.entities.keys() - active:
            self.entities.pop(key).removeNode()

    def update_game(self, task):
        dt = min(.1, ClockObject.getGlobalClock().getDt())
        state = self.snapshot
        if self.screen == "game" and state["state"] in ("playing", "paused"):
            if state["state"] == "playing" and self.mouseWatcherNode.hasMouse() and self.mouseWatcherNode.isButtonDown(MouseButton.three()):
                mouse_x = self.mouseWatcherNode.getMouseX()
                if self.mouse_x is not None:
                    self.yaw += (mouse_x - self.mouse_x) * self.sensitivity
                self.mouse_x = mouse_x
            self.accumulator += dt
            while self.accumulator >= 1/60:
                if state["state"] == "playing":
                    self.yaw += 2*(("arrow_right" in self.keys)-("arrow_left" in self.keys))
                self.frames.clear()
                pressed = {action: key in self.keys for action, key in self.bindings.items()}
                self.frames[state["tick"]] = {
                    "move": [pressed["right"]-pressed["left"], pressed["forward"]-pressed["back"]],
                    "cam_yaw_deg": self.yaw, **{action: pressed[action] for action in
                                               ("jump", "dash", "interact", "pulse", "pause")},
                }
                previous = state
                self.snapshot = state = next(self.steps)
                if state["sim_tick"] != previous["sim_tick"]:
                    if previous["player"]["grounded"] and state["player"]["vel"][1] > 0 and pressed["jump"]:
                        self.play_sound("jump")
                    if math.ceil(state["time_left_s"]) <= 10 and math.ceil(state["time_left_s"]) < math.ceil(previous["time_left_s"]):
                        self.play_sound("countdown")
                    if self.night == 3 and state["sim_tick"] % 1800 == 1680:
                        self.play_sound("wind")
                self.accumulator -= 1/60
                if state["state"] in ("won","lost"):
                    break
        player = state["player"]
        place(self.player, player["pos"])
        angle = math.radians(self.yaw)
        x, y, z = player["pos"]
        self.camera.setPos(x-10*math.sin(angle),z-10*math.cos(angle),y+5.6)
        self.camera.lookAt(x+3*math.sin(angle),z+3*math.cos(angle),y+1.3)
        if self.screen in ("menu", "intro"):
            self.fog.setLinearRange(56, 155)
            orbit = 0 if self.reduce_motion else task.time * .075
            center = 35 if self.night == 2 else 0
            distance = 112 if self.night == 2 else 75
            self.camera.setPos(center + distance*math.sin(orbit), -distance*math.cos(orbit), 42)
            self.camera.lookAt(center, 0, -1)
        else:
            self.fog.setLinearRange(24, 88)
        light = sum(entry["lit"] for entry in state["lanterns"])
        intensity = .15 + .55*light/len(state["lanterns"])
        self.ambient.setColor((intensity, intensity*.85, intensity*.79, 1))
        if light:
            nearest_lit = min((entry for entry in state["lanterns"] if entry["lit"]),
                              key=lambda entry: ground_distance(player["pos"], entry["pos"]))
            lx, ly, lz = nearest_lit["pos"]
            self.lantern_glow.setPos(lx, lz, ly + 2.3)
            self.world.setLight(self.lantern_glow)
        else:
            self.world.clearLight(self.lantern_glow)
        for entry in state["lanterns"]:
            paper, meter, tear = self.lanterns[entry["id"]]
            if entry["lit"]:
                blink = .55 if not self.reduce_motion and entry["fuel"] < 30 and state["sim_tick"] % 60 >= 30 else 1
                paper.setScale(1)
                paper.setLightOff()
                paper.setColorScale(blink,.92*blink,.66*blink,1)
                meter.setSx(max(.001,entry["fuel"]/100))
                meter.setColor(blink,.59*blink,.23*blink,1)
                meter.show()
                tear.hide()
            else:
                paper.setScale(.8)
                paper.setZ(.44)
                paper.setColorScale(.39,.37,.57,1)
                meter.hide()
                tear.show()
            if entry["lit"]:
                paper.setZ(0)
        for node, charm in zip(self.charm_nodes, state["charms"]):
            node.show() if charm["available"] else node.hide()
        self.draw_entities(state)
        minute, second = divmod(math.ceil(state["time_left_s"]), 60)
        self.hud.setText(f"FLAMES  {player['flames']}     {minute:02}:{second:02}     LANTERNS  {light}/{len(state['lanterns'])}     SCORE  {state['score']}")
        warning = state["time_left_s"] <= 30 or any(entry["lit"] and entry["fuel"] < 30 for entry in state["lanterns"])
        self.hud.setFg((1,1,1,1) if warning and self.easy_palette else
                       (1,.353,.373,1) if warning else (1,.90,.71,1))
        candidates = [entry for entry in state["lanterns"] if not entry["lit"] or entry["fuel"] < 100]
        hint = f"LIGHT  {player['carried']}/{player['capacity']}     DASH  {player['dash_cd_s']:.1f}s     PULSE  {player['pulse_cd_s']:.1f}s"
        if warning and self.easy_palette:
            hint = "(!)  " + hint
        if state["time_left_s"] <= 10:
            hint = "LAST 10 SECONDS   |   " + hint
        if self.night == 3 and state["sim_tick"] % 1800 >= 1680:
            hint = "WIND APPROACHING   |   " + hint
        spawned = next((shade for shade in state["shades"] if shade["state"] == "spawning"), None)
        if spawned is not None:
            self.spawn_hint_until = state["sim_tick"] + 120
            self.spawn_hint_pos = spawned["pos"]
        self.direction.hide()
        if state["sim_tick"] < self.spawn_hint_until:
            hint = "SHADE APPEARED   |   " + hint
            sx, _, sz = self.spawn_hint_pos
            bearing = math.atan2(sx-x, sz-z) - angle
            horizontal, vertical = math.sin(bearing), math.cos(bearing)
            self.direction.setPos(horizontal * self.getAspectRatio() * .89, vertical * .80)
            self.direction.setRoll(math.degrees(math.atan2(vertical,horizontal)))
            self.direction.show()
        if candidates:
            nearest = min(candidates,key=lambda entry: (ground_distance(entry["pos"],player["pos"]), entry["id"]))
            if ground_distance(nearest["pos"],player["pos"]) <= self.tuning["interact_radius"]:
                cost = self.tuning["relight_cost"] if nearest["ever_lit"] else self.tuning["lantern_cost"]
                key = self.bindings["interact"].upper()
                hint += f"     {key}  Refuel ({nearest['fuel']:.0f}/100)" if nearest["lit"] else f"     {key}  Deposit ({nearest['deposited']}/{cost})"
        self.prompt.setText(hint)
        title, label = "", ""
        if self.screen == "menu":
            title, label = "DAO DEN LONG", "Play 3D"
        elif self.screen == "intro":
            title, label = ("Night I  /  Cloud Harbor","Night II  /  Bamboo Crossing","Night III  /  Bell Tower")[self.night-1], "Enter night"
        elif self.screen == "dawn":
            title, label = f"Dawn  /  {self.total_score}", "Main menu"
        elif self.screen == "scores":
            label = "Main menu"
        elif state["state"] == "won":
            title, label = "The island shines", "Continue"
        elif state["state"] == "lost":
            title, label = "The night has ended", "Try again"
        elif state["state"] == "paused":
            title = f"Paused  /  {self.bindings['pause']}: resume  R: restart  M: menu"
        if self.screen == "controls":
            title, label = "", ""
            self.controls_text.setText(
                "CONTROLS\nForward Back Left Right Jump Dash Interact Pulse Pause\n"
                f"{self.controls_message}"
            )
            for widget in self.controls_widgets():
                widget.show()
        else:
            self.controls_text.setText("")
            for widget in self.controls_widgets():
                widget.hide()
        self.title.setText(title)
        if self.screen == "menu":
            self.hud.setText("")
            self.prompt.setText("L: Leaderboard")
        if self.screen == "scores":
            self.score_board.setText("LEADERBOARD\n" + ("\n".join(
                f"{index:2}.  {entry['name']}  {entry['score']}"
                for index, entry in enumerate(self.leaderboard_entries, 1)) or "No scores yet"))
            self.button.setZ(-.35)
        else:
            self.score_board.setText("")
            self.button.setZ(-.21)
        if not self.saved_score and (self.screen == "dawn" or
                                    self.screen == "game" and state["state"] == "lost"):
            self.score_entry.show()
            self.score_button.show()
        else:
            self.score_entry.hide()
            self.score_button.hide()
        if label:
            self.button["text"] = label
            self.button.show()
        else:
            self.button.hide()
        return task.cont


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-leaderboard", type=Path)
    args = parser.parse_args()
    if args.export_leaderboard:
        export_scores(args.export_leaderboard)
    else:
        LanternIsland().run()

