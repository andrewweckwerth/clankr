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
                ids = container_ids(args.project_name)
                if ids:
                    raw = command_output(["docker", "stats", "--no-stream", "--format", "{{json .}}", *ids])
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
