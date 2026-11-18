"""A simplified implementation of the Unix grep utility.

The public entry point is :func:`grep`, which searches fixed strings in the
provided files and returns the matching lines as a single string.
"""


def _parse_flags(flags):
    """Return the set of single-letter flags supplied to grep."""
    if flags is None:
        return set()
    if isinstance(flags, str):
        tokens = flags.split()
    else:
        tokens = flags

    parsed = set()
    for token in tokens:
        token = str(token)
        if not token:
            continue
        if token.startswith("-"):
            parsed.update(token[1:])
        else:
            parsed.update(token)
    return parsed


def grep(pattern, flags, files):
    """Search *files* for *pattern* and return all selected lines.

    Supported flags are ``-n`` (line numbers), ``-l`` (file names only),
    ``-i`` (case-insensitive), ``-v`` (invert selection), and ``-x`` (match
    entire lines).
    """
    flag_set = _parse_flags(flags)
    show_line_numbers = "n" in flag_set
    list_files = "l" in flag_set
    case_insensitive = "i" in flag_set
    invert = "v" in flag_set
    entire_line = "x" in flag_set

    if case_insensitive:
        pattern_to_match = pattern.casefold()
    else:
        pattern_to_match = pattern

    show_filenames = len(files) > 1
    listed_files = []
    output_lines = []

    for file_name in files:
        with open(file_name) as current_file:
            lines = current_file.read().splitlines()

        file_matched = False
        for line_number, line in enumerate(lines, start=1):
            comparable_line = line.casefold() if case_insensitive else line
            if entire_line:
                matched = comparable_line == pattern_to_match
            else:
                matched = pattern_to_match in comparable_line

            if invert:
                matched = not matched

            if not matched:
                continue

            if list_files:
                file_matched = True
                break

            parts = []
            if show_filenames:
                parts.append("{0}:".format(file_name))
            if show_line_numbers:
                parts.append("{0}:".format(line_number))
            parts.append(line)
            output_lines.append("".join(parts) + "\n")

        if list_files and file_matched:
            listed_files.append(file_name)

    if list_files:
        return "".join("{0}\n".format(file_name) for file_name in listed_files)
    return "".join(output_lines)
