import base64
import json
import re

from minisweagent.models.utils.openai_multimodal import DEFAULT_MULTIMODAL_REGEX, expand_multimodal_content


IMAGE_INSTRUCTION = """
You can inspect task-visible images. Print an inline image from a bash command using this upstream format:
<MSWEA_MULTIMODAL_CONTENT><CONTENT_TYPE>image_url</CONTENT_TYPE>data:image/jpeg;base64,BASE64_DATA</MSWEA_MULTIMODAL_CONTENT>
Use an available image library to encode JPEG/PNG/WebP. Keep each observation to at most four images,
one megabyte total decoded bytes, and label frame numbers or image names in adjacent text.
For video, sample visible frames or contact sheets and inspect the relevant motion before designing a detector.
Images are passed directly to the same selected model. No auxiliary vision service is used.
"""


def split_image_output(text):
    matches = list(re.finditer(DEFAULT_MULTIMODAL_REGEX, text))
    if "<MSWEA_MULTIMODAL_CONTENT>" in text and not matches:
        raise ValueError("Incomplete inline image marker")
    if any(match.group(1).strip() != "image_url" for match in matches):
        raise ValueError("Only image_url inline content is supported")
    parts = expand_multimodal_content({"content": text}, pattern=DEFAULT_MULTIMODAL_REGEX)["content"]
    images = [part for part in parts if part["type"] == "image_url"]
    if len(images) > 4:
        raise ValueError("At most four inline images are allowed per observation")
    cleaned = "".join(part["text"] if part["type"] == "text" else "[inline image attached]" for part in parts)
    if "<MSWEA_MULTIMODAL_CONTENT>" in cleaned:
        raise ValueError("An inline image marker was not parsed completely")
    return cleaned, images


def native_image_turn(history):
    clean_history, images, total_bytes = [], [], 0
    for message in history:
        content = message.get("content")
        if not isinstance(content, list):
            clean_history.append(message)
            continue
        text = []
        for part in content:
            if part["type"] == "text":
                text.append(part["text"])
                continue
            if part["type"] != "image_url":
                raise ValueError("Unexpected multimodal input block")
            matched = re.fullmatch(r"data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)",
                                   part["image_url"]["url"])
            if not matched:
                raise ValueError("Images must be inline JPEG/PNG/WebP data; external URLs are not fetched")
            media_type, encoded = matched.groups()
            decoded = base64.b64decode(encoded, validate=True)
            magic_matches = {"image/jpeg": decoded.startswith(b"\xff\xd8\xff"),
                             "image/png": decoded.startswith(b"\x89PNG\r\n\x1a\n"),
                             "image/webp": decoded.startswith(b"RIFF") and decoded[8:12] == b"WEBP"}
            if not magic_matches[media_type]:
                raise ValueError("The inline image bytes do not match the declared media type")
            total_bytes += len(decoded)
            if total_bytes > 1_000_000 or len(images) >= 4:
                raise ValueError("One user turn may contain at most four images and one megabyte")
            images.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": encoded}})
            text.append(f"[attached image {len(images)}]")
        clean_history.append(message | {"content": "\n".join(text)})
    if not images:
        return None, 0
    turn = {"type": "user", "message": {"role": "user", "content": [
        {"type": "text", "text": json.dumps(clean_history, ensure_ascii=False)}, *images]}}
    return json.dumps(turn, ensure_ascii=False) + "\n", len(images)
