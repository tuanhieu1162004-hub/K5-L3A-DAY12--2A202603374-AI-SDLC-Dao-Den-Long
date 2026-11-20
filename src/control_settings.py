"""Persist and validate the Panda3D accessibility controls."""

import json
from pathlib import Path


PATH = Path.home() / ".dao-den-long-controls.json"
DEFAULT = dict(forward="w", back="s", left="a", right="d", jump="space", dash="shift",
               interact="e", pulse="q", pause="escape")
KEYS = (set("abcdefghijklmnopqrstuvwxyz0123456789") - {"l", "m", "r"}) | {
    "space", "shift", "escape", "tab", "arrow_up", "arrow_down",
}


def parse(text):
    keys = text.lower().split()
    if len(keys) != len(DEFAULT) or any(key not in KEYS for key in keys):
        raise ValueError("Enter nine supported key names.")
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate key: each action needs a different key.")
    return dict(zip(DEFAULT, keys))


def load():
    try:
        data = json.loads(PATH.read_text(encoding="utf-8"))
        return (parse(data["keys"]), data.get("large") is True, data.get("reduced") is True,
                max(0,min(100,int(data.get("volume",70)))), max(25,min(200,int(data.get("sensitivity",100)))))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return DEFAULT.copy(), False, False, 70, 100


def save(bindings, large, reduced, volume, sensitivity):
    temporary = PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps({"keys":" ".join(bindings.values()),
                                     "large":large,"reduced":reduced,"volume":volume,
                                     "sensitivity":sensitivity}), encoding="utf-8")
    temporary.replace(PATH)
