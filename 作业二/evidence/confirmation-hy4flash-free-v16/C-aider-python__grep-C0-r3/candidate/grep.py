"""A simplified grep implementation supporting fixed-string searches."""


def _parse_flags(flags):
    if not flags:
        return set()
    if isinstance(flags, str):
        return set(flags.split())
    if isinstance(flags, (list, tuple, set)):
        return set(flags)
    return {flags}


def grep(pattern, flags, files):
    flags = _parse_flags(flags)

    ignore_case = "-i" in flags
    invert = "-v" in flags
    entire_line = "-x" in flags
    names_only = "-l" in flags
    line_numbers = "-n" in flags

    needle = pattern.lower() if ignore_case else pattern
    multiple_files = len(files) > 1
    results = []

    for file_name in files:
        with open(file_name) as file:
            for number, line in enumerate(file.read().splitlines(), start=1):
                candidate = line.lower() if ignore_case else line
                matches = (
                    candidate == needle
                    if entire_line
                    else needle in candidate
                )
                if invert:
                    matches = not matches
                if not matches:
                    continue

                if names_only:
                    results.append(file_name + "\n")
                    break

                parts = []
                if multiple_files:
                    parts.append(file_name)
                if line_numbers:
                    parts.append(str(number))
                prefix = ":".join(parts) + ":" if parts else ""
                results.append(prefix + line + "\n")

    return "".join(results)
