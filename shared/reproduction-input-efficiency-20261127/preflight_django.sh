set -euo pipefail
cd "$(dirname "$0")/../.."
project_root="$PWD"
job="$project_root/work/input-efficiency-20261126/django-preflight"
trap 'printf "%s\n" "$?" > "$job.exit"' EXIT
mkdir -p "$project_root/work/input-efficiency-20261126/preflight"
export DOCKER_HOST=unix://[server-project]/guest/docker.sock
export DOCKER_CONFIG="$project_root/work/docker-config"
export PATH="$project_root/work/vendor/docker:$PATH"
export PYTHONPATH="$project_root/work/input-efficiency-20261126/runtime:$project_root"
export MSWEA_GLOBAL_CONFIG_DIR="$project_root/work/miniswe-config"
export MSWEA_SILENT_STARTUP=1
cd "$project_root/work/input-efficiency-20261126/runtime"
"$project_root/work/.venv/bin/python" -m course_eval.preflight \
    --manifest "$project_root/work/input-efficiency-20261126/candidate-tasks.json" \
    --sources "$project_root/work/datasets" --id django__django-14855 \
    --out "$project_root/work/input-efficiency-20261126/preflight/django__django-14855" \
    > "$job.log" 2>&1
