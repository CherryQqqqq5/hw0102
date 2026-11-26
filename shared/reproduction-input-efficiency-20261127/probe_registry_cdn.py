import json
import time
from pathlib import Path
from urllib.parse import urlparse

import requests


FOLDER = Path(__file__).parent.resolve()
record = json.loads((FOLDER / "preparation/django__django-14855/record.json").read_text())
manifest = json.loads((FOLDER / "preparation/django__django-14855/manifest.json").read_text())
repository = record["source"].removeprefix("docker.io/").split("@")[0]
layer = manifest["layers"][0]["digest"]
with requests.Session() as session:
    session.trust_env = False
    session.proxies = {"http": "http://127.0.0.1:46671", "https": "http://127.0.0.1:46671"}
    response = session.get("https://auth.docker.io/token", params={"service": "registry.docker.io",
        "scope": "repository:" + repository + ":pull"}, timeout=(10, 30))
    response.raise_for_status()
    token = response.json()["token"]
    response = session.get("https://registry-1.docker.io/v2/" + repository + "/blobs/" + layer,
        headers={"Authorization": "Bearer " + token}, allow_redirects=False, timeout=(10, 30))
    if response.status_code not in {302, 307}:
        raise RuntimeError("The public registry did not return its layer CDN location")
    location = response.headers["Location"]
with requests.Session() as direct:
    direct.trust_env = False
    started = time.monotonic()
    with direct.get(location, headers={"Range": "bytes=0-1048575"}, stream=True, timeout=(10, 20)) as response:
        response.raise_for_status()
        count = 0
        for chunk in response.iter_content(65536):
            count += len(chunk)
            if count >= 1048576:
                break
        result = {"cdn_host": urlparse(location).hostname, "status": response.status_code,
            "direct_bytes": count, "seconds": time.monotonic() - started, "new_model_calls": 0}
(FOLDER / "registry-cdn-qualification.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result), flush=True)
