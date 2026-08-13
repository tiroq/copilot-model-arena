# Copilot Model Benchmark

Run identical tasks in isolated copies, then audit every result twice.

`./benchmark.sh run` runs 2 models x 3 tasks. `./benchmark.sh audit` runs the two configured judges. Results are written under `results/`.

Set model IDs and judge IDs in `.env`. Requires `copilot`, `git`, `jq`, Python 3.
