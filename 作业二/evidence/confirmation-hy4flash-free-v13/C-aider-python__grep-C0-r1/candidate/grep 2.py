"""A simplified fixed-string version of the Unix grep command."""


_LONG_FLAGS = {
    "line-number": "n",
    "files-with-matches": "l",
    "ignore-case": "i",
    "invert-match": "v",
    "line-regexp": "x",
}


def _parse_flags(flags):
    """Return a set of single-letter flags from a string or iterable."""
    if not flags:
        return set()

    if isinstance(flags, str):
        tokens = flags.split()
    else:
        tokens = []
        for flag in flags:
            if isinstance(flag, str):
                tokens.extend(flag.split())

    parsed = set()
    for token in tokens:
        if token.startswith("--"):
            long_name = token[2:]
            if long_name in _LONG_FLAGS:
                parsed.add(_LONG_FLAGS[long_name])
        elif token.startswith("-"):
            parsed.update(char for char in token[1:] if char != "-")
    return parsed


def grep(pattern, flags, files):
    """Return the lines from ``files`` that match the fixed string ``pattern``."""
    active_flags = _parse_flags(flags)
    files = list(files)
    show_line_numbers = "n" in active_flags
    list_files = "l" in active_flags
    case_insensitive = "i" in active_flags
    invert = "v" in active_flags
    whole_line = "x" in active_flags
    multiple_files = len(files) > 1

    needle = pattern.lower() if case_insensitive else pattern
    result = []

    for filename in files:
        found_match = False

        with open(filename) as current_file:
            for line_number, raw_line in enumerate(current_file, start=1):
                line = raw_line[:-1] if raw_line.endswith("\n") else raw_line
                haystack = line.lower() if case_insensitive else line

                if whole_line:
                    matches = haystack == needle
                else:
                    matches = needle in haystack

                if invert:
                    matches = not matches

                if not matches:
                    continue

                if list_files:
                    found_match = True
                    break

                parts = []
                if multiple_files:
                    parts.append(str(filename))
                if show_line_numbers:
                    parts.append(str(line_number))
                parts.append(line)
                result.append(":".join(parts) + "\n")

        if list_files and found_match:
            result.append(str(filename) + "\n")

    return "".join(result)
