#!/usr/bin/env bash
# Compare Demucs worker replica counts using production images in an isolated
# Compose project on the same Docker host. It never starts Traefik or frontend.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
environment_file="${BENCHMARK_ENV_FILE:-$repo_root/benchmarks/.env.benchmark}"
run_id=""
audio_path=""
jobs=""
replicas=""
sample_interval="${BENCHMARK_STATS_INTERVAL_SECONDS:-5}"
timeout_seconds="${BENCHMARK_TIMEOUT_SECONDS:-7200}"
cleanup="true"
enable_emulation="false"

usage() {
  cat <<'EOF'
Usage:
  BENCHMARK_ENV_FILE=benchmarks/.env.benchmark \
    ./benchmarks/run_demucs_benchmark.sh \
      --audio benchmarks/fixtures/clip.wav --jobs 1000 --demucs-replicas 1 [--run-id name] [--enable-emulation] [--keep-project]

The audio file must be below benchmarks/fixtures so it can be mounted read-only
  inside the isolated benchmark runner. On Apple Silicon, use
  --enable-emulation to run amd64 production images under Docker Desktop.
  The script removes its isolated containers, network, and volumes when it
  exits. Pass --keep-project only when you need to inspect them after the run.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --audio) audio_path="${2:-}"; shift 2 ;;
    --jobs) jobs="${2:-}"; shift 2 ;;
    --demucs-replicas) replicas="${2:-}"; shift 2 ;;
    --run-id) run_id="${2:-}"; shift 2 ;;
    --enable-emulation) enable_emulation="true"; shift ;;
    --keep-project) cleanup="false"; shift ;;
    --cleanup) cleanup="true"; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

[[ -n "$audio_path" && -n "$jobs" && -n "$replicas" ]] || { usage >&2; exit 2; }
[[ "$jobs" =~ ^[1-9][0-9]*$ ]] || { echo "--jobs must be a positive integer" >&2; exit 2; }
[[ "$replicas" =~ ^[1-9][0-9]*$ ]] || { echo "--demucs-replicas must be a positive integer" >&2; exit 2; }
[[ -f "$environment_file" ]] || { echo "Benchmark environment file not found: $environment_file" >&2; exit 2; }
grep -Eq '^BENCHMARK_ENVIRONMENT=isolated$' "$environment_file" || {
  echo "Refusing to run without BENCHMARK_ENVIRONMENT=isolated in the benchmark environment file" >&2
  exit 2
}

environment_value() {
  local key="$1"
  sed -n "s/^${key}=//p" "$environment_file" | head -n 1
}

image_prefix="$(environment_value IMAGE_PREFIX)"
if [[ "$image_prefix" == ghcr.io/* ]]; then
  case "$(uname -m)" in
    arm64|aarch64)
      if [[ "$enable_emulation" != "true" ]]; then
        echo "Published production images are linux/amd64, but this host is $(uname -m)." >&2
        echo "Rerun with --enable-emulation for a functional local smoke test." >&2
        echo "Use an amd64 host for performance measurements." >&2
        exit 2
      fi
      ;;
  esac
fi

if [[ -z "$run_id" ]]; then
  run_id="demucs-$(date -u +%Y%m%dT%H%M%SZ)-${replicas}x-${jobs}jobs"
fi
[[ "$run_id" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]*$ ]] || { echo "--run-id may only use letters, numbers, ., _, and -" >&2; exit 2; }

audio_absolute="$(cd "$(dirname "$audio_path")" && pwd)/$(basename "$audio_path")"
fixture_root="$repo_root/benchmarks/fixtures"
case "$audio_absolute" in
  "$fixture_root"/*) audio_in_container="/fixtures/${audio_absolute#"$fixture_root"/}" ;;
  *) echo "--audio must live under $fixture_root" >&2; exit 2 ;;
esac

project_name="clankr-bench-$run_id"
project_name="$(printf '%s' "$project_name" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_-]/-/g')"
output_dir="$repo_root/benchmarks/results/$run_id"
[[ ! -e "$output_dir" ]] || { echo "Refusing to overwrite existing result directory: $output_dir" >&2; exit 2; }
mkdir -p "$output_dir/logs"

benchmark_platform=""
if [[ "$enable_emulation" == "true" ]]; then
  benchmark_platform="linux/amd64"
  echo "Using linux/amd64 emulation for this benchmark run"
fi
compose=(docker compose --project-name "$project_name" --env-file "$environment_file" -f "$repo_root/docker-compose.prod.yml" -f "$repo_root/benchmarks/docker-compose.benchmark.yml")
compose_command() {
  if [[ -n "$benchmark_platform" ]]; then
    DOCKER_DEFAULT_PLATFORM="$benchmark_platform" ENV_FILE="$environment_file" BENCHMARK_RUN_ID="$run_id" "${compose[@]}" "$@"
  else
    ENV_FILE="$environment_file" BENCHMARK_RUN_ID="$run_id" "${compose[@]}" "$@"
  fi
}

cleanup_stats() {
  if [[ -n "${stats_pid:-}" ]] && kill -0 "$stats_pid" 2>/dev/null; then
    kill "$stats_pid" 2>/dev/null || true
    wait "$stats_pid" 2>/dev/null || true
  fi
}

cleanup_on_exit() {
  exit_status=$?
  cleanup_stats
  if [[ "$exit_status" -ne 0 && "$cleanup" == "true" ]]; then
    echo "Benchmark failed; removing its partial isolated project" >&2
    compose_command down --volumes --remove-orphans >/dev/null 2>&1 || true
  fi
  exit "$exit_status"
}
trap cleanup_on_exit EXIT

git_sha="$(git -C "$repo_root" rev-parse HEAD)"
python3 - "$output_dir/manifest.json" "$run_id" "$project_name" "$jobs" "$replicas" "$audio_absolute" "$git_sha" <<'PY'
import json
import platform
import sys
from datetime import datetime, timezone

path, run_id, project, jobs, replicas, audio, git_sha = sys.argv[1:]
payload = {
    "run_id": run_id,
    "compose_project": project,
    "scenario": "demucs",
    "submitted_jobs": int(jobs),
    "demucs_replicas": int(replicas),
    "audio_path": audio,
    "git_sha": git_sha,
    "started_at": datetime.now(timezone.utc).isoformat(),
    "host": platform.platform(),
}
with open(path, "w") as output:
    json.dump(payload, output, indent=2)
    output.write("\n")
PY

compose_command config >/dev/null
if [[ "$image_prefix" == ghcr.io/* ]]; then
  echo "Pulling benchmark application images from $image_prefix"
  compose_command pull redis db minio minio_init orchestrator demucs
fi
compose_command build benchmark-runner
compose_command up -d --no-build --scale "demucs=$replicas" redis db minio minio_init demucs orchestrator

demucs_container="$(docker ps -q --filter "label=com.docker.compose.project=$project_name" --filter "label=com.docker.compose.service=demucs" | head -n 1)"
demucs_image="$(docker inspect --format '{{.Config.Image}}' "$demucs_container")"
demucs_image_id="$(docker inspect --format '{{.Image}}' "$demucs_container")"
python3 - "$output_dir/manifest.json" "$demucs_image" "$demucs_image_id" <<'PY'
import json
import sys

path, image, image_id = sys.argv[1:]
with open(path) as source:
    payload = json.load(source)
payload["demucs_image"] = image
payload["demucs_image_id"] = image_id
with open(path, "w") as output:
    json.dump(payload, output, indent=2)
    output.write("\n")
PY

for _ in $(seq 1 90); do
  if compose_command exec -T orchestrator curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
compose_command exec -T orchestrator curl -fsS http://localhost:8000/health >/dev/null || {
  echo "The isolated orchestrator did not become healthy. Inspect: docker compose -p $project_name logs" >&2
  exit 1
}

python3 "$repo_root/benchmarks/collect_docker_stats.py" \
  --project-name "$project_name" \
  --output "$output_dir/docker-stats.ndjson" \
  --interval-seconds "$sample_interval" &
stats_pid=$!

compose_command run --rm benchmark-runner submit \
  --run-id "$run_id" \
  --audio "$audio_in_container" \
  --jobs "$jobs" \
  --demucs-replicas "$replicas" 2>&1 | tee "$output_dir/logs/benchmark-runner-submit.log"
compose_command run --rm benchmark-runner wait \
  --run-id "$run_id" \
  --timeout-seconds "$timeout_seconds" 2>&1 | tee "$output_dir/logs/benchmark-runner-wait.log"

cleanup_stats
unset stats_pid

while IFS= read -r container_id; do
  container_name="$(docker inspect --format '{{.Name}}' "$container_id" | sed 's#^/##; s#[^A-Za-z0-9._-]#-#g')"
  docker logs --timestamps "$container_id" >"$output_dir/logs/$container_name.log" 2>&1 || true
done < <(docker ps -aq --filter "label=com.docker.compose.project=$project_name")

compose_command run --rm benchmark-runner import-events \
  --run-id "$run_id" \
  --logs "/results/$run_id/logs"
compose_command run --rm benchmark-runner report \
  --run-id "$run_id" \
  --output "/results/$run_id"

if [[ "$cleanup" == "true" ]]; then
  compose_command down --volumes
  echo "Benchmark complete: $output_dir/report.md"
  echo "Removed the isolated benchmark project, network, and database volumes. Results remain in $output_dir"
else
  echo "Benchmark complete: $output_dir/report.md"
  echo "Isolated Compose project retained for inspection: $project_name"
  echo "Clean it up with: docker compose --project-name $project_name --env-file $environment_file -f docker-compose.prod.yml -f benchmarks/docker-compose.benchmark.yml down --volumes"
fi
