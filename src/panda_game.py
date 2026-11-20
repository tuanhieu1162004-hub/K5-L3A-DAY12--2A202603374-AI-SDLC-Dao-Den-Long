"""Panda3D frontend for the shared simulation."""

import json
import math
import random
import sys
from pathlib import Path

from direct.gui.DirectGui import DirectButton
from direct.gui.OnscreenText import OnscreenText
from direct.showbase.ShowBase import ShowBase
from panda3d.core import AmbientLight, CardMaker, ClockObject, DirectionalLight, Fog, PointLight, WindowProperties

from headless import CONTRACT_PATH, ground_distance, initial_state, simulation_steps
from night_features import CHARM_POINTS
from night_maps import PADS
from panda_scene import island, keeper, landscape, lantern, model, place

PALETTE_PATH = Path.home() / ".dao-den-long-palette.json"


class LanternIsland(ShowBase):
    def __init__(self):
        super().__init__()
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
        for key in ("w", "a", "s", "d", "space", "e", "q", "shift", "escape", "p", "arrow_left", "arrow_right"):
            self.accept(key, self.keys.add, [key])
            self.accept(f"{key}-up", self.keys.discard, [key])
        self.accept("enter", self.continue_game)
        self.accept("r", self.restart_night)
        self.accept("m", self.main_menu)
        self.accept("f2", self.toggle_palette)
        try:
            self.easy_palette = json.loads(PALETTE_PATH.read_text(encoding="utf-8")) is True
        except (OSError, ValueError):
            self.easy_palette = False
        self.tuning = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))["tuning"]
        self.hud = OnscreenText(text="", pos=(0, .87), scale=.047, fg=(1,.90,.71,1), mayChange=True)
        self.prompt = OnscreenText(text="", pos=(0, -.74), scale=.044, fg=(1,.85,.53,1), mayChange=True)
        self.help = OnscreenText(text="WASD  |  Left/Right  |  Space  |  Shift  |  E  |  Q  |  Esc  |  F2: palette",
                                 pos=(0, -.94), scale=.043, fg=(.83,.80,.92,1))
        self.title = OnscreenText(text="", pos=(0, .16), scale=.095, fg=(1,.78,.43,1), mayChange=True)
        self.button = DirectButton(text="Play", scale=.072, pos=(0,0,-.21), command=self.continue_game,
                                   frameColor=(.96,.71,.35,1), text_fg=(.12,.09,.15,1))
        self.world = None
        self.main_menu()
        self.taskMgr.add(self.update_game, "game loop")

    def toggle_palette(self):
        self.easy_palette = not self.easy_palette
        try:
            PALETTE_PATH.write_text(json.dumps(self.easy_palette), encoding="utf-8")
        except OSError:
            pass

    def main_menu(self):
        self.night = 1
        self.total_score = 0
        self.restart_night()
        self.screen = "menu"

    def restart_night(self):
        self.keys.clear()
        self.frames = {}
        self.yaw = 0
        self.accumulator = 0
        self.steps = simulation_steps(None, sys.maxsize, 1, self.tuning, self.frames,
                                      initial_state({}, 42, self.tuning, self.night))
        self.snapshot = next(self.steps)
        self.screen = "game"
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
        elif self.screen == "dawn":
            self.main_menu()

    def draw_entities(self, state):
        active = set()
        for kind, data in (("mote", state["motes"]), ("shade", state["shades"]), ("drifter", state["drifters"])):
            for entity in data:
                key = (kind, entity["id"])
                active.add(key)
                if key not in self.entities:
                    if kind == "mote":
                        node = model(self.world,kind,[(0,.37),(.13,.49),(0,.61)],[(1,.81,.32)],6)
                        node.setLightOff()
                    elif kind == "shade":
                        node = model(self.world,kind,[(0,-.8),(.44,-.58),(.66,.14),(.33,.65),(0,.83)],
                                     [(.25,.13,.34),(.33,.17,.43),(.19,.11,.30)],8)
                        accent = model(node,"accent",[(0,-.26),(.65,-.09),(.68,.02),(0,.12)],[(1,1,1)],8)
                        accent.setLightOff()
                        for x in (-.21,.21):
                            eye = model(accent,"eye",[(0,.16),(.09,.24),(0,.34)],[(1,1,1)],8)
                            eye.setPos(x,-.61,0)
                    else:
                        node = model(self.world,kind,[(0,-.12),(.43,.03),(.29,.19),(0,.28)],[(.48,.77,.79)],6)
                    self.entities[key] = node
                node = self.entities[key]
                place(node, entity["pos"])
                if kind == "mote":
                    node.setZ(node.getZ() + .13*math.sin(state["sim_tick"]*.1 + node.getX()))
                elif kind == "shade":
                    node.setColorScale(1.45,1.45,1.65,1) if entity["state"] == "stunned" else node.clearColorScale()
                    node.lookAt(self.camera)
                    node.setP(0)
                    node.find("accent").setColor((0,.702,1,1) if self.easy_palette else (.478,.235,1,1))
        for key in self.entities.keys() - active:
            self.entities.pop(key).removeNode()

    def update_game(self, task):
        dt = min(.1, ClockObject.getGlobalClock().getDt())
        state = self.snapshot
        if self.screen == "game" and state["state"] in ("playing", "paused"):
            self.accumulator += dt
            while self.accumulator >= 1/60:
                if state["state"] == "playing":
                    self.yaw += 2*(("arrow_right" in self.keys)-("arrow_left" in self.keys))
                self.frames.clear()
                self.frames[state["tick"]] = {
                    "move": [("d" in self.keys)-("a" in self.keys), ("w" in self.keys)-("s" in self.keys)],
                    "cam_yaw_deg": self.yaw, "jump": "space" in self.keys, "dash": "shift" in self.keys,
                    "interact": "e" in self.keys, "pulse": "q" in self.keys, "pause": bool(self.keys & {"escape","p"}),
                }
                self.snapshot = state = next(self.steps)
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
            orbit = task.time * .075
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
                blink = .55 if entry["fuel"] < 30 and state["sim_tick"] % 60 >= 30 else 1
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
        if candidates:
            nearest = min(candidates,key=lambda entry: (ground_distance(entry["pos"],player["pos"]), entry["id"]))
            if ground_distance(nearest["pos"],player["pos"]) <= self.tuning["interact_radius"]:
                cost = self.tuning["relight_cost"] if nearest["ever_lit"] else self.tuning["lantern_cost"]
                hint += f"     E  Refuel ({nearest['fuel']:.0f}/100)" if nearest["lit"] else f"     E  Deposit ({nearest['deposited']}/{cost})"
        self.prompt.setText(hint)
        title, label = "", ""
        if self.screen == "menu":
            title, label = "DAO DEN LONG", "Play 3D"
        elif self.screen == "intro":
            title, label = ("Night I  /  Cloud Harbor","Night II  /  Bamboo Crossing","Night III  /  Bell Tower")[self.night-1], "Enter night"
        elif self.screen == "dawn":
            title, label = f"Dawn  /  {self.total_score}", "Main menu"
        elif state["state"] == "won":
            title, label = "The island shines", "Continue"
        elif state["state"] == "lost":
            title, label = "The night has ended", "Try again"
        elif state["state"] == "paused":
            title = "Paused  /  Esc: resume  R: restart  M: menu"
        self.title.setText(title)
        if label:
            self.button["text"] = label
            self.button.show()
        else:
            self.button.hide()
        return task.cont


if __name__ == "__main__":
    LanternIsland().run()

