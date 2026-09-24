"""Write one JSON resource sample per running container until interrupted."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def command_output(command: list[str]) -> str:
    return subprocess.run(command, check=True, text=True, capture_output=True).stdout


def container_ids(project_name: str) -> list[str]:
    output = command_output(
        ["docker", "ps", "-q", "--filter", f"label=com.docker.compose.project={project_name}"]
    )
    return output.split()


def collect_stats(project_name: str) -> str:
    ids = container_ids(project_name)
    if not ids:
        return ""
    try:
        return command_output(["docker", "stats", "--no-stream", "--format", "{{json .}}", *ids])
    except subprocess.CalledProcessError as exc:
        errors = (exc.stderr or "").strip().splitlines()
        if not errors or not all("No such container:" in line for line in errors):
            raise
        # One-shot Compose runners can be removed after `docker ps` returns.
        # Keep any samples Docker produced and refresh the IDs next interval.
        print("A container disappeared during sampling; continuing next interval.", file=sys.stderr)
        return exc.stdout or ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--interval-seconds", type=float, default=5)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a") as file:
        try:
            while True:
                raw = collect_stats(args.project_name)
                if raw:
                    sampled_at = datetime.now(timezone.utc).isoformat()
                    for line in raw.splitlines():
                        sample = json.loads(line)
                        sample["timestamp"] = sampled_at
                        file.write(json.dumps(sample, separators=(",", ":")) + "\n")
                    file.flush()
                time.sleep(args.interval_seconds)
        except KeyboardInterrupt:
            return
        except subprocess.CalledProcessError as exc:
            print(exc.stderr, file=sys.stderr)
            raise


if __name__ == "__main__":
    main()
