"""A stand-in for svrngs's API, as the helper meets it: a loopback HTTP server
that answers `/v1/groups`, `/v1/lends` and `POST /v1/lends/<name>/approve`
only with the right bearer token, and refuses any request carrying `Origin`
or `Sec-Fetch-Site`, as svrngs does (svrngs api.rs:199-210). `mode` makes it
answer the ways svrngs can go wrong, and "old" as an svrngs from before
approving, which has no approve route (surface.rs `router` at v1.12.2).
"""

import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = "fake-token-0123456789abcdef"

GROUPS = {
    "groups": [
        {"id": "a" * 64, "name": "WorkingGroup", "person": "LittleMac", "left": False},
        {"id": "b" * 64, "name": "<img src=x>" + "x" * 300, "person": "Ana", "left": False},
    ],
    "key": "c" * 64,
}

U32, U64 = 2**32 - 1, 2**64 - 1


def approving(body):
    """The body as svrngs's approve route takes it (surface.rs `Approving`,
    `#[serde(deny_unknown_fields)]`: `token` a string, `pid` a u32 and
    `start` a u64, each or both null or absent), or None, which axum's
    `Json` answers 422 in plain text."""
    try:
        asked = json.loads(body)
    except ValueError:
        return None
    number = lambda v, most: v is None or (isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= most)
    fits = (isinstance(asked, dict) and set(asked) <= {"token", "pid", "start"} and isinstance(asked.get("token"), str)
            and number(asked.get("pid"), U32) and number(asked.get("start"), U64))
    return asked if fits else None
LENDS = {
    "lent": [
        {"person": "Fedora", "name": "deepseek-flash", "kind": "spot", "origin": "http://abc.localhost:41097/", "using": 0, "limit": None}
    ],
    "unanswered": [],
}


class Fake:
    def __init__(self, mode="running"):
        self.mode = mode
        self.seen = []
        # Lends' labels that answer as a model, and the model names they give.
        self.models = {}
        # Lends' labels whose program does not answer: svrngs says 502.
        self.down = set()
        # Seconds each /v1/lends takes, as a lender slow to answer makes it.
        self.delay = 0
        self.lends = LENDS
        # This computer's lends as approving reads them: by name, its port,
        # the token what answers there now is listed with, the processes
        # holding it (pid: start) and what svrngs shows of them.
        self.ports = {}
        self.approved = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def answer(self, status, body, kind="application/json"):
                raw = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                fake.seen.append({"path": self.path, "headers": dict(self.headers)})
                if self.headers.get("Origin") or self.headers.get("Sec-Fetch-Site"):
                    return self.answer(403, {"error": "this API answers programs on this computer, not pages"})
                if self.headers.get("Authorization") != f"Bearer {TOKEN}":
                    return self.answer(401, {"error": "no token"})
                if fake.mode == "error":
                    return self.answer(500, {"error": "the record could not be read"})
                if fake.mode == "not-json":
                    return self.answer(200, b"<html>a proxy's page</html>", "text/html")
                if fake.mode == "huge":
                    return self.answer(200, {"groups": [], "pad": "x" * (300 * 1024)})
                host = self.headers.get("Host", "")
                if host.endswith(f".localhost:{fake.port}"):
                    label = host.split(".")[0]
                    if label in fake.models and self.path == "/v1/models":
                        return self.answer(200, {"object": "list", "data": [{"id": m} for m in fake.models[label]]})
                    if label in fake.down:
                        return self.answer(502, {"error": "the lend's program did not answer"})
                    return self.answer(404, b"Not Found", "text/plain")
                if self.path == "/v1/groups":
                    return self.answer(200, GROUPS)
                if self.path.startswith("/v1/lends?namespace=") and fake.delay:
                    time.sleep(fake.delay)
                if self.path.startswith("/v1/lends?namespace="):
                    # The first group's lends; the second lends nothing.
                    first = self.path.endswith("a" * 64)
                    return self.answer(200, fake.lends if first else {"lent": [], "unanswered": []})
                return self.answer(404, {"error": "no such route"})

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                fake.seen.append({"path": self.path, "headers": dict(self.headers), "body": body})
                if self.headers.get("Origin") or self.headers.get("Sec-Fetch-Site"):
                    return self.answer(403, {"error": "this API answers programs on this computer, not pages"})
                if self.headers.get("Authorization") != f"Bearer {TOKEN}":
                    return self.answer(401, {"error": "no token"})
                if self.path == "/v1/open":
                    asked = json.loads(body or b"{}")
                    label = asked.get("lend") or "svrngs"
                    return self.answer(200, {"open": f"http://{label}.localhost:{fake.port}/svrngs-open?code=one-time-secret"})
                named = re.fullmatch(r"/v1/lends/([^/?]+)/approve", self.path)
                if named and fake.mode != "old":
                    return self.approve(named.group(1), body)
                # axum's own answer to a route it doesn't have: 404, no body.
                return self.answer(404, b"", "text/plain")

            def approve(self, name, body):
                """svrngs surface.rs `approve` and share.rs `approve`, in
                their order: the body, the lend, the process chosen (by
                `pid` and `start` together, or none), then the token."""
                if self.headers.get("Content-Type") != "application/json":
                    return self.answer(415, b"Expected request with `Content-Type: application/json`", "text/plain")
                asked = approving(body)
                if asked is None:
                    return self.answer(422, b"Failed to deserialize the JSON body into the target type", "text/plain")
                closed = lambda words: self.answer(403, {"error": words, "kind": "closed"})
                lend = fake.ports.get(name)
                if lend is None:
                    return closed(f"nothing is shared from a port here by the name {name}")
                port, pid, start = lend["port"], asked.get("pid"), asked.get("start")
                if pid is not None and start is not None:
                    if lend["processes"].get(pid, start) != start:
                        return closed(f"svrngs can't share port {port}: that program stopped; choose it again.")
                    if pid not in lend["processes"]:
                        return closed(f"svrngs can't share port {port}: another program also listens on port {port}. Stop it, or choose that one, then share it again.")
                if asked["token"] != lend["token"]:
                    return closed(f"svrngs can't share port {port}: what answers on port {port} changed; choose it again.")
                fake.approved.append(name)
                return self.answer(200, {"name": name, "answers": lend["answers"]})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
