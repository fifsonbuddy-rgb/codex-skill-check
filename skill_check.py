"""Check the skills and command hooks advertised by a local Codex app server."""

import argparse
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time


def receive(stream, responses):
    try:
        for line in stream:
            responses.put(json.loads(line))
    except (ValueError, OSError):
        pass
    finally:
        responses.put(None)


def send(process, method, params=None, identifier=None):
    message = {"method": method}
    if params is not None:
        message["params"] = params
    if identifier is not None:
        message["id"] = identifier
    process.stdin.write(json.dumps(message) + "\n")
    process.stdin.flush()


def request(process, responses, method, params, identifier):
    send(process, method, params, identifier)
    deadline = time.monotonic() + 30
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(f"{method} timed out")
        try:
            message = responses.get(timeout=remaining)
        except queue.Empty:
            raise RuntimeError(f"{method} timed out") from None
        if not isinstance(message, dict):
            raise RuntimeError(f"App server closed or returned invalid data during {method}")
        if message.get("id") == identifier:
            if "error" in message:
                raise RuntimeError(f"{method}: {message['error'].get('message', 'request failed')}")
            return message["result"]


def entries(result, field):
    groups = result["data"]
    if len(groups) != 1:
        raise ValueError("Expected one result for the requested workspace")
    group = groups[0]
    if group["errors"]:
        raise ValueError(f"Codex reported {len(group['errors'])} discovery error(s) for {field}")
    return group[field]


def inspect(args):
    folder = args.cwd.resolve(strict=True)
    if not folder.is_dir():
        raise ValueError("Workspace must be a directory")
    params = {"cwds": [str(folder)]}
    with tempfile.TemporaryDirectory() as db:
        command = [args.codex, "app-server", "-c", "sqlite_home=" + json.dumps(Path(db).as_posix(), ensure_ascii=False)]
        with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, encoding="utf-8", cwd=folder) as process:
            responses = queue.Queue()
            reader = threading.Thread(target=receive, args=(process.stdout, responses), daemon=True)
            reader.start()
            try:
                request(process, responses, "initialize", {
                    "clientInfo": {"name": "codex_skill_check", "version": "1.0"},
                    "capabilities": {"experimentalApi": True},
                }, 1)
                send(process, "initialized")
                result = request(process, responses, "skills/list", {**params, "forceReload": True}, 2)
                skills = {item["name"] for item in entries(result, "skills") if item["enabled"]}
                hooks = []
                if args.hook_contains:
                    result = request(process, responses, "hooks/list", params, 3)
                    hooks = [item["command"].casefold() for item in entries(result, "hooks")
                             if item.get("handlerType") == "command" and item["enabled"]]
                return skills, hooks
            finally:
                process.stdin.close()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                reader.join(timeout=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", type=Path, default=Path.cwd(), help="workspace to inspect")
    parser.add_argument("--codex", default="codex", help="Codex executable name or absolute path")
    parser.add_argument("--skill", action="append", default=[], help="required enabled skill name (repeatable)")
    parser.add_argument("--hook-contains", action="append", default=[], metavar="TEXT",
                        help="required substring in an enabled command hook (repeatable)")
    args = parser.parse_args()
    if any(not text.strip() for text in args.hook_contains + args.skill):
        parser.error("checks require nonempty names or search text")
    try:
        skills, hooks = inspect(args)
    except (OSError, RuntimeError, KeyError, TypeError, ValueError, AttributeError) as exc:
        print(f"Discovery failed: {exc}", file=sys.stderr)
        return 2
    if not (args.skill or args.hook_contains):
        print(f"{len(skills)} enabled skill(s)")
        for name in sorted(skills):
            print(name)
        return 0
    checks = [(f"skill {name}", name in skills) for name in args.skill]
    for text in args.hook_contains:
        checks.append((f"command hook containing {text!r}", any(text.casefold() in hook for hook in hooks)))
    for label, found in checks:
        print(f"{'OK' if found else 'MISSING'}  {label}")
    return 0 if all(found for _, found in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
