#!/usr/bin/python3 -I
"""A fully seeded svrngs, as the plugin's helper would answer it, for the
preview image. Its people are svrngs's page-test fixture's (web/tests/
grouped.mjs: Alex, Sam, Kim, Ana, House and the Welcome room), with more
groups and lends so the panel looks as it does in daily use."""
import json
import sys

PORT = 41097


def origin(label):
    return f"http://{label}.localhost:{PORT}/"


def lend(person, name, kind, label, answering=True, carried=False):
    return {"person": person, "name": name, "kind": kind, "origin": origin(label),
            "using": 0, "limit": None, "answering": answering, "carried": carried}


HOUSE, LISBON, CLIMBING, WELCOME = "1" * 64, "2" * 64, "3" * 64, "4" * 64
GROUPS = [
    {"id": HOUSE, "name": "House", "person": "Alex", "left": False},
    {"id": LISBON, "name": "Trip to Lisbon", "person": "Alex", "left": False},
    {"id": CLIMBING, "name": "Climbing", "person": "Alex", "left": False},
    {"id": WELCOME, "name": "Welcome room", "person": "Alex", "left": False},
]
LENDS = {
    HOUSE: {"lent": [
        lend("Sam", "jellyfin", "jellyfin", "sam1"),
        lend("Sam", "navidrome", "navidrome", "sam2"),
        lend("Sam", "coder", "llama-server", "sam3"),
        lend("Kim", "immich", "immich", "kim1"),
        lend("Kim", "paperless", "paperless", "kim2"),
        lend("Ana", "actual", "actual", "ana1", answering=False),
        lend("Alex", "library", "calibre-web", "alex1"),
        lend("Alex", "Money", "money", "c1", carried=True),
        lend("Alex", "Events", "events", "c2", carried=True),
        lend("Alex", "House-rules", "house-rules", "c3", carried=True),
        lend("Alex", "Movie-Night", "movie-night", "c4", carried=True),
    ], "unanswered": []},
    LISBON: {"lent": [
        lend("Ana", "itinerary", "python3", "ana2"),
        lend("Sam", "photos", "immich", "sam4"),
        lend("Alex", "Money", "money", "c5", carried=True),
    ], "unanswered": []},
    CLIMBING: {"lent": [
        lend("Kim", "route-log", "python3", "kim3"),
        lend("Kim", "vision", "llama-server", "kim4"),
        lend("Alex", "Events", "events", "c6", carried=True),
    ], "unanswered": ["Ravi"]},
    WELCOME: {"lent": [lend("Sam", "notes", "python3", "sam5")], "unanswered": []},
}
STATE = {
    "svrngs": "running", "groups": GROUPS, "command": True, "groupsCut": False,
    "mine": [{"name": "library", "port": 8083, "groups": [HOUSE], "readable": True}],
    "lends": LENDS,
    "listeners": [{"port": 3000, "program": "puma", "name": "garden", "pid": 1, "start": 1}],
}
MODELS = {"ok": True, "asked": 3, "lends": [
    {"person": "Sam", "name": "coder", "group": "House", "label": "sam3", "address": origin("sam3") + "v1", "models": ["qwen3-coder-30b"]},
    {"person": "Kim", "name": "vision", "group": "Climbing", "label": "kim4", "address": origin("kim4") + "v1", "models": ["qwen2.5-vl-7b"]},
    {"person": "Sam", "name": "jellyfin", "group": "House", "label": "sam1", "address": origin("sam1") + "v1", "models": []},
]}
MODELS["models"] = [l for l in MODELS["lends"] if l["models"]]

verb = sys.argv[1] if len(sys.argv) > 1 else ""
print(json.dumps(STATE if verb == "state" else MODELS if verb == "models" else {"ok": True, "said": ""}))
