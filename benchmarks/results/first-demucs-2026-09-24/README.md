# First Demucs benchmark artifacts

These are the five valid runs used by [`docs/first-benchmark-results.md`](../../../docs/first-benchmark-results.md).
They were copied from the supplied result folder and are kept as raw benchmark
evidence, separate from the ignored live output directory at `benchmarks/results/`.

Each run contains:

- `manifest.json` — host, checkout, image, fixture, and run identity.
- `summary.json` — aggregate completion, queue, processing, and latency metrics.
- `jobs.csv` — one row per submitted job with raw timestamps and durations.
- `docker-stats.ndjson` — collected Docker resource samples.
- `analysis.json` — derived CPU and memory summaries.
- `report.md` — the benchmark runner's short report.

Only the complete 10-job runs with zero failures are included. Logs and audio
fixtures remain outside the repository.
