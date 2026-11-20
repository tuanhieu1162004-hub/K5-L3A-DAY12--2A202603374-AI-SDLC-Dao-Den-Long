"""Persistent local top ten for the three-night campaign."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path


SCORES_PATH = Path.home() / ".dao-den-long-leaderboard.json"


def scores():
    try:
        entries = json.loads(SCORES_PATH.read_text(encoding="utf-8"))["entries"]
        return sorted(entries, key=lambda entry: (-entry["score"], entry["achieved_at"]))[:10]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def record_score(name, score, nights_won, seed):
    if re.fullmatch(r"[A-Za-z0-9_]{3,12}", name) is None:
        raise ValueError("Use 3–12 letters, numbers or underscores.")
    entries = scores()
    entries.append({
        "name": name, "score": score, "nights_won": nights_won,
        "achieved_at": datetime.now(timezone.utc).isoformat(), "seed": seed,
    })
    entries.sort(key=lambda entry: (-entry["score"], entry["achieved_at"]))
    temporary = SCORES_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps({"entries": entries[:10]}, indent=2) + "\n", encoding="utf-8")
    temporary.replace(SCORES_PATH)


def export_scores(path):
    Path(path).write_text(json.dumps({"entries": scores()}, indent=2) + "\n", encoding="utf-8")
