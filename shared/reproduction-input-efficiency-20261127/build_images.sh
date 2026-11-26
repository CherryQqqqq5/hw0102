set -euo pipefail
cd "$(dirname "$0")/../.."
export DOCKER_HOST=unix://[server-project]/guest/docker.sock
export DOCKER_CONFIG="$PWD/work/docker-config"
export DOCKER_BUILDKIT=1
export HTTP_PROXY=http://127.0.0.1:46671
export HTTPS_PROXY=http://127.0.0.1:46671
export NO_PROXY=localhost,127.0.0.1,::1
trap 'printf "%s\n" "$?" > work/input-efficiency-20261126/image-build.exit' EXIT
for target in javascript python cpp; do
    work/vendor/docker/docker build --target "$target" --platform linux/amd64 --network host \
        --build-arg HTTP_PROXY=http://10.0.2.2:46671 --build-arg HTTPS_PROXY=http://10.0.2.2:46671 \
        --build-arg http_proxy=http://10.0.2.2:46671 --build-arg https_proxy=http://10.0.2.2:46671 \
        -f work/vmshare/aider/aider.Dockerfile -t "nju-course-aider:$target" work/vmshare/aider \
        > "work/input-efficiency-20261126/aider-$target-image.log" 2>&1
done
