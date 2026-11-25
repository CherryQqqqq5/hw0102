import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import requests


def registry_tool_environment(root):
    return {"PATH": os.environ["PATH"], "REGCTL_CONFIG": str(root / "work/registry-tools/regctl.json"),
        "DOCKER_CONFIG": str(root / "work/registry-tools/docker"),
        "HTTPS_PROXY": "http://127.0.0.1:7890", "HTTP_PROXY": "http://127.0.0.1:7890",
        "NO_PROXY": "production.cloudfront.docker.com,production.cloudflare.docker.com",
        "TMPDIR": str(root / "work/process-tmp")}


def main():
    root = Path.cwd()
    binary = root / "work/vendor/bin/regctl"
    manifest = root / "work/registry-tools/tool.json"
    if binary.exists() or manifest.exists():
        raise FileExistsError("The tool is already present; inspect its pinned manifest instead of reinstalling")
    version = "v0.11.6"
    url = "https://api.github.com/repos/regclient/regclient/releases/tags/" + version
    with requests.Session() as session:
        session.trust_env = False
        session.proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
        metadata = session.get(url, timeout=(5, 20))
        metadata.raise_for_status()
        release = metadata.json()
        asset, = [row for row in release["assets"] if row["name"] == "regctl-darwin-arm64"]
        expected = asset.get("digest", "")
        if release["tag_name"] != version or not expected.startswith("sha256:"):
            raise ValueError("The official release lacks its required immutable asset digest")
        temporary = binary.with_suffix(".partial")
        checksum = hashlib.sha256()
        size = 0
        started = time.monotonic()
        with session.get(asset["browser_download_url"], stream=True, timeout=(5, 30)) as response:
            response.raise_for_status()
            with temporary.open("xb") as handle:
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > asset["size"] or time.monotonic() - started > 300:
                        raise RuntimeError("The public tool download exceeded its declared size or bounded time")
                    checksum.update(chunk)
                    handle.write(chunk)
    if "sha256:" + checksum.hexdigest() != expected or size != asset["size"]:
        raise ValueError("The downloaded official tool differs from its release digest")
    temporary.chmod(0o755)
    temporary.replace(binary)
    checked = subprocess.run([str(binary), "version"], env=registry_tool_environment(root),
                             capture_output=True, text=True, check=True, timeout=15)
    if version not in checked.stdout:
        raise ValueError("The downloaded tool reports a different release version")
    record = {"name": "regctl", "version": version, "platform": "darwin/arm64", "release_api": url,
        "download_url": asset["browser_download_url"], "sha256": checksum.hexdigest(), "bytes": size,
        "version_output": checked.stdout, "isolated_empty_registry_configuration": True,
        "user_registry_or_docker_credentials_used": False, "new_model_calls": 0,
        "source": "https://github.com/regclient/regclient/tree/" + version}
    manifest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    main()
