import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--proxy", required=True)
    args = parser.parse_args()
    directory = args.root / "bin"
    directory.mkdir(parents=True, exist_ok=True)
    binary = directory / "regctl"
    record_path = directory / "regctl.json"
    if binary.exists() or record_path.exists():
        raise FileExistsError("Inspect the existing project tool before installing another")
    version = "v0.11.6"
    with requests.Session() as session:
        session.trust_env = False
        session.proxies = {"http": args.proxy, "https": args.proxy}
        response = session.get("https://api.github.com/repos/regclient/regclient/releases/tags/" + version,
            timeout=(10, 60))
        response.raise_for_status()
        release = response.json()
        asset, = [row for row in release["assets"] if row["name"] == "regctl-linux-amd64"]
        if release["tag_name"] != version or not asset.get("digest", "").startswith("sha256:"):
            raise RuntimeError("The official Linux tool lacks its immutable release identity")
        response = session.get(asset["browser_download_url"], timeout=(10, 120))
        response.raise_for_status()
        body = response.content
    checksum = hashlib.sha256(body).hexdigest()
    if len(body) != asset["size"] or "sha256:" + checksum != asset["digest"]:
        raise RuntimeError("The downloaded Linux tool differs from its official release")
    binary.write_bytes(body)
    binary.chmod(0o700)
    actual = subprocess.check_output([str(binary), "version"], text=True, timeout=15,
        env=os.environ | {"REGCTL_CONFIG": str(args.root / "preparation/regctl.json")})
    if version not in actual:
        raise RuntimeError("The actual tool version differs")
    record = {"version": version, "platform": "linux/amd64", "sha256": checksum,
        "bytes": len(body), "source": asset["browser_download_url"], "new_model_calls": 0}
    record_path.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
