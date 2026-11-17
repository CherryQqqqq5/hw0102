"""A simplified, fixed-string version of the Unix grep command."""


def _parse_flags(flags):
    """Return the supported grep flags as a set of '-x' style tokens."""
    if flags is None:
        tokens = []
    elif isinstance(flags, str):
        tokens = flags.split()
    else:
        tokens = list(flags)

    parsed = set()
    for token in tokens:
        if not isinstance(token, str) or not token.startswith("-"):
            continue
        # Accept both spaced flags ("-n -i") and combined flags ("-ni").
        for character in token[1:]:
            parsed.add("-" + character)
    return parsed


def grep(pattern, flags, files):
    options = _parse_flags(flags)

    list_files = "-l" in options
    show_line_numbers = "-n" in options
    case_insensitive = "-i" in options
    invert = "-v" in options
    exact_line = "-x" in options
    include_filenames = len(files) > 1

    needle = pattern.casefold() if case_insensitive else pattern
    results = []

    for file_name in files:
        with open(file_name) as source:
            lines = source.readlines()

        selected = []
        for line_number, line in enumerate(lines, start=1):
            content = line[:-1] if line.endswith("\n") else line
            haystack = content.casefold() if case_insensitive else content

            matches = needle in haystack
            if exact_line:
                matches = needle == haystack
            if invert:
                matches = not matches

            if matches:
                selected.append((line_number, content))

        if list_files:
            if selected:
                results.append(file_name + "\n")
            continue

        for line_number, content in selected:
            prefix = ""
            if include_filenames:
                prefix += file_name + ":"
            if show_line_numbers:
                prefix += str(line_number) + ":"
            results.append(prefix + content + "\n")

    return "".join(results)
