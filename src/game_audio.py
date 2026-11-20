"""Short synthesized interface sounds."""

import math
import struct
import tempfile
import wave
from pathlib import Path

try:
    import winsound
except ImportError:
    winsound = None


TONES = {
    "mote_picked": (960,), "lantern_lit": (523, 659, 784), "pulse": (720, 480),
    "player_hit": (220, 150), "jump": (420, 620), "dash": (820, 530),
    "won": (523, 659, 784, 1047), "lost": (392, 330, 262),
    "shade_spawned": (130, 165), "countdown": (880,), "wind": (260, 310),
    "ambient": (196, 294, 247, 196, 165, 247, 220, 147),
}


def write_wave(path, cue, volume):
    samples = bytearray()
    rate = 16000
    for tone in TONES[cue]:
        length = 12800 if cue == "ambient" else 960
        level = 18 if cue == "ambient" else 75
        for index in range(length):
            envelope = min(1, index / 80, (length - index) / 160)
            amplitude = level * volume * envelope
            samples.extend(struct.pack("<h", int(amplitude * math.sin(math.tau * tone * index / rate))))
    with wave.open(str(path), "wb") as sound:
        sound.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        sound.writeframes(samples)


class GameAudio:
    def __init__(self, root):
        self.root = root
        self.directory = None

    def play(self, cue, volume):
        if not volume or cue not in TONES:
            return
        if winsound is None:
            if cue != "ambient":
                self.root.bell()
            return
        try:
            if self.directory is None:
                self.directory = tempfile.TemporaryDirectory()
            path = Path(self.directory.name) / f"{cue}-{volume}.wav"
            if not path.exists():
                write_wave(path, cue, volume)
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except (OSError, RuntimeError):
            pass
