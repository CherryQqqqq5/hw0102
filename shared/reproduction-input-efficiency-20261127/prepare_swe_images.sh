set -euo pipefail
cd "$(dirname "$0")/../.."
export COURSE_STUDY_DOCKER_HOST=unix://[server-project]/guest/docker.sock
export PYTHONPATH="$PWD/work/input-efficiency-20261126/runtime:$PWD"
trap 'printf "%s\n" "$?" > work/input-efficiency-20261126/swe-images.exit' EXIT
for task in pytest-dev__pytest-7571 django__django-14170 pydata__xarray-6461 scikit-learn__scikit-learn-14710; do
    work/.venv/bin/python work/input-efficiency-20261126/prepare_image.py --task "$task"
done
