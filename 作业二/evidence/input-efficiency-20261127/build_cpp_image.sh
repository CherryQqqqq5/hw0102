set -euo pipefail
cd "$(dirname "$0")/../.."
export DOCKER_HOST=unix://[server-project]/guest/docker.sock
export DOCKER_CONFIG="$PWD/work/docker-config"
export DOCKER_BUILDKIT=1
export HTTP_PROXY=http://127.0.0.1:46671
export HTTPS_PROXY=http://127.0.0.1:46671
export NO_PROXY=localhost,127.0.0.1,::1
if [ -f work/input-efficiency-20261126/image-build.exit ]; then
    mv work/input-efficiency-20261126/image-build.exit work/input-efficiency-20261126/image-build-first-attempt.exit
fi
trap 'printf "%s\n" "$?" > work/input-efficiency-20261126/image-build.exit' EXIT
cp work/vmshare/aider/aider-cpp-test.sh work/input-efficiency-20261126/cpp-image/
work/vendor/docker/docker build --target cpp --platform linux/amd64 --network host \
    --build-arg HTTP_PROXY= --build-arg HTTPS_PROXY= --build-arg http_proxy= --build-arg https_proxy= \
    -t nju-course-aider:cpp work/input-efficiency-20261126/cpp-image \
    > work/input-efficiency-20261126/aider-cpp-mirror-image.log 2>&1
