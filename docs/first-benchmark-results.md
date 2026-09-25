# First benchmark results: Demucs with 1x–5x workers

*First pass — September 24–25, 2026 (UTC)*

I wanted to see whether adding Demucs workers on the same VM would get more work done, or whether they would mostly compete for the same resources. This is an initial comparison, not a final capacity estimate.

## Benchmark Process

I used the Linveo VM hosting Clankr: 6 CPU cores, 16 GB RAM, and 100 GB storage. Production Clankr stayed running, but there was no user traffic during the benchmarks.

Each run submitted 10 jobs using the same song, “U Don't Know” by RP Boo. I ran one batch at each worker count: 1, 2, 3, 4, and 5. 


This benchmark measured the Demucs stage only: downloading audio from MinIO, separating vocals with `htdemucs`, and uploading the vocal output.
## Results and how to read them

All five runs completed 10/10 jobs with zero recorded failures. Times are rounded; the raw results are in [`benchmarks/results/first-demucs-2026-09-24/`](../benchmarks/results/first-demucs-2026-09-24/).

| Workers | Whole batch | Jobs/hour equivalent | Median queue wait | Median processing | Median submission → completion |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1x | 35.86 min | 16.73 | 16.94 min | 3.51 min | 20.42 min |
| 2x | 27.07 min | 22.16 | 11.42 min | 5.29 min | 16.63 min |
| 3x | 26.52 min | 22.63 | 8.19 min | 7.90 min | 16.29 min |
| 4x | 25.74 min | 23.31 | 10.01 min | 10.08 min | 19.52 min |
| 5x | 25.23 min | 23.78 | 5.99 min | 12.03 min | 18.48 min |

Whole batch is the time from the first job being created to the last one finishing. Queue wait is time before a worker starts; processing is Demucs runtime; submission → completion is both together.
## Analysis

Five workers finished the batch fastest: 25.23 minutes versus 35.86 with one, saving about 10.63 minutes. Most of the improvement happened between one and two workers. Going from two to five saved another 1.84 minutes, while median processing time increased from 5.29 to 12.03 minutes.

Adding workers cleared the batch faster, but each job took longer to process. The shorter queue can offset that slower processing for users. Three workers had the lowest median submission-to-completion time in this trial, while five workers had the shortest whole-batch time.

The small 10-job batch may affect every worker comparison. More containers can process more jobs at once, but with few jobs some containers may sit idle while still adding overhead. For example, five workers can all process jobs in both rounds, while four workers leave only two active for the final two jobs. Seems like more containers is better but more benchmarking will be needed for better analysis.

## Next steps

The next report should use more songs, more jobs, repeated trials, and both evenly and unevenly divisible batch sizes. I also want two scenarios: a realistic workload that resembles normal use, and a larger stress test that measures how the system behaves under sustained pressure.
