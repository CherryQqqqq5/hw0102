import re
import shlex


def rejection_reason(command):
    # 只覆盖已识别的明文shell/Python读法，不把此检查当作完整安全沙箱。
    try:
        normalized = " ".join(shlex.split(command))
    except ValueError:
        normalized = command
    for text in (command, normalized):
        if re.search(r"\b(?:cat|tac|nl|head|tail|less|more|bat|sed|awk|grep|egrep|fgrep|rg|strings|xxd|hexdump|base64|cp)\b[^\n;|]*(?:forward\.py|forward\*|\*\.py)", text):
            return "Oracle implementation file reads/copies are not allowed;import only the public callable."
        if ("forward.py" in text or ("forward" in text and "__file__" in text)) and re.search(
                r"\bopen\s*\(|\.read_(?:text|bytes)\s*\(|\.readlines\s*\(|\blinecache\.", text):
            return "Reading oracle source through Python file APIs is not allowed."
        if re.search(r"\.\s*(?:A1|A2|b1|b2|__globals__|__dict__)\b|\bgetattr\s*\([^,]+,\s*['\"](?:A1|A2|b1|b2|__globals__|__dict__)['\"]", text):
            return "Direct oracle weights or globals are not an allowed query API."
        if re.search(r"\binspect\s*\.|\b(?:getsource|getsourcelines|getsourcefile|getfile|getmembers|vars|dir)\s*\(|\bdis\s*\.\s*dis\s*\(", text):
            return "Oracle implementation/globals inspection is not allowed in this query-only task."
    return None
