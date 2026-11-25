"""A small fixed-string grep implementation."""


def grep(pattern, flags, files):
    """Search files for lines matching *pattern* and return matching lines.

    Supported flags (which may be combined or space-separated):

    -n  Prepend the line number (after the filename, if present).
    -l  Print only the names of files containing at least one match.
    -i  Perform a case-insensitive comparison.
    -v  Invert the match (return lines that do not match).
    -x  Match only when the search string equals the entire line.
    """
    # Normalize e.g. "-n -i -x" as well as combined forms like "-nix".
    options = set(flags.replace("-", "").replace(" ", ""))

    list_only = "l" in options
    number_lines = "n" in options
    ignore_case = "i" in options
    invert_match = "v" in options
    whole_line = "x" in options

    if ignore_case:
        pattern = pattern.lower()

    prefix_files = len(files) > 1
    output = []
    files_with_matches = []

    for filename in files:
        with open(filename) as source:
            lines = source.read().splitlines()

        has_match = False

        for line_number, line in enumerate(lines, start=1):
            candidate = line.lower() if ignore_case else line
            if whole_line:
                matches = candidate == pattern
            else:
                matches = pattern in candidate
            if invert_match:
                matches = not matches

            if matches:
                has_match = True
                if list_only:
                    break
                parts = []
                if prefix_files:
                    parts.append(filename)
                if number_lines:
                    parts.append(str(line_number))
                parts.append(line)
                output.append(":".join(parts))

        if list_only and has_match:
            files_with_matches.append(filename)

    if list_only:
        return "".join(filename + "\n" for filename in files_with_matches)

    return "".join(line + "\n" for line in output)
