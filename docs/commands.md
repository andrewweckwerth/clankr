# Handy VM and benchmark commands

Commands below use the current VM (`104.234.124.211`), VM checkout
(`/opt/clankr/app`), and Mac checkout (`~/Repos/clankr`). Update these paths if
the deployment moves. Each section says which computer should run the command.

## 1. Connect to the VM — from your Mac

```bash
ssh root@104.234.124.211
cd /opt/clankr/app
```

The `cd` runs on the VM after SSH connects. Use `exit` to return to your Mac.
For file transfers, open a second Mac terminal so the benchmark can keep running
in the first one.

## 2. Check the benchmark setup — on the VM

```bash
cd /opt/clankr/app
git status --short
git log -1 --oneline
ls -l benchmarks/.env.benchmark
ls -lh benchmarks/fixtures/
df -h /
```

Make sure the checkout includes the resource-collector fix before benchmarking.
The production deployment workflow updates this checkout after a merge to
`main`; unmerged changes on your Mac do not reach the VM automatically.

If the benchmark environment file does not exist, create it once:

```bash
cp benchmarks/.env.benchmark.example benchmarks/.env.benchmark
chmod 600 benchmarks/.env.benchmark
nano benchmarks/.env.benchmark
```

Replace the placeholder secrets with benchmark-only values. Keep
`BENCHMARK_ENVIRONMENT=isolated` and set `IMAGE_TAG` to a published commit tag
for repeatable comparisons. Do not use the production environment file.
See [benchmarking.md](benchmarking.md) for the complete setup.

## 3. Copy audio to the VM — from your Mac

Audio fixtures are ignored by Git, so they must be transferred separately.
This copies the existing song to a simple filename used in the commands below:

```bash
ssh root@104.234.124.211 'mkdir -p /opt/clankr/app/benchmarks/fixtures'
scp "$HOME/Repos/clankr/benchmarks/fixtures/U-Don't No.wav" \
  root@104.234.124.211:/opt/clankr/app/benchmarks/fixtures/representative.wav
```

`representative.wav` now refers to the copied file. Repeating the transfer
overwrites that destination file. Always quote paths containing spaces or
apostrophes. If the shell displays `>` instead of running your command, press
**Control+C** and retry with the path in double quotes.

## 4. Run 10 Demucs jobs with one worker — on the VM

```bash
cd /opt/clankr/app

BENCHMARK_ENV_FILE=benchmarks/.env.benchmark \
  ./benchmarks/run_demucs_benchmark.sh \
  --audio benchmarks/fixtures/representative.wav \
  --jobs 10 \
  --demucs-replicas 1
```

This runs only Demucs plus its supporting services, not the full audio pipeline.
It uses isolated benchmark data but shares the VM's CPU, memory, and disk with
production. Run during a quiet period and leave the SSH session open until the
script finishes. The default completion timeout is two hours.

Each invocation creates a new run ID and results directory. On a successful
run, the script exports reports and removes the isolated containers and volumes.
Look for `Benchmark complete` and verify the report files exist; a progress
line alone does not mean report generation has finished.

## 5. Compare with two workers — on the VM

After the first run finishes, use the same audio, image tag, and job count:

```bash
BENCHMARK_ENV_FILE=benchmarks/.env.benchmark \
  ./benchmarks/run_demucs_benchmark.sh \
  --audio benchmarks/fixtures/representative.wav \
  --jobs 10 \
  --demucs-replicas 2
```

Run comparisons sequentially so the benchmarks do not compete with each other.

## 6. Download results — from your Mac

Copy all runs into `~/Downloads/clankr-benchmarks/results/`:

```bash
mkdir -p "$HOME/Downloads/clankr-benchmarks"
scp -r root@104.234.124.211:/opt/clankr/app/benchmarks/results \
  "$HOME/Downloads/clankr-benchmarks/"
```

To download just one run, replace `RUN_ID` with its directory name:

```bash
scp -r root@104.234.124.211:/opt/clankr/app/benchmarks/results/RUN_ID \
  "$HOME/Downloads/clankr-benchmarks/"
```

The single-run command places `RUN_ID` directly under `clankr-benchmarks`,
without the extra `results/` directory.

## 7. Open or generate the HTML report — on your Mac

For the all-runs download above, replace `RUN_ID` with the run you want:

```bash
open "$HOME/Downloads/clankr-benchmarks/results/RUN_ID/analysis.html"
```

If the HTML report is missing but `docker-stats.ndjson` contains usable samples:

```bash
python3 "$HOME/Repos/clankr/benchmarks/analyze_benchmark.py" \
  --run "$HOME/Downloads/clankr-benchmarks/results/RUN_ID"
open "$HOME/Downloads/clankr-benchmarks/results/RUN_ID/analysis.html"
```

The HTML shows CPU and memory samples. Job timings and completion counts are
in `report.md`, `summary.json`, and `jobs.csv`. Generating HTML cannot recover
missing samples or missing final job reports.

## Disk usage and image cleanup — on the VM

```bash
df -h /
docker system df
```

For a more detailed Docker breakdown:

```bash
docker system df -v
```

To remove images that no existing container uses:

```bash
docker image prune -a
```

Docker asks for confirmation. This leaves containers and volumes intact, but
unused images for previous deployments or future benchmarks will need to be
downloaded again. Recheck free space with `df -h /` afterward.
