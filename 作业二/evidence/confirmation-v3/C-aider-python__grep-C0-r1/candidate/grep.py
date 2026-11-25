def _split_lines(content):
    """Split file content into lines the way a line-oriented tool does.

    Only '\\n' terminates a line (matching grep), and a trailing newline
    at the end of the file does not produce a spurious empty final line.
    """
    if content == "":
        return []
    lines = content.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def grep(pattern, flags, files):
    flag_set = set(flags.split())

    invert = "-v" in flag_set
    ignore_case = "-i" in flag_set
    exact = "-x" in flag_set
    show_number = "-n" in flag_set
    names_only = "-l" in flag_set

    multiple_files = len(files) > 1

    needle = pattern.lower() if ignore_case else pattern

    output = []

    for fname in files:
        with open(fname) as f:
            content = f.read()

        file_matched = False

        for number, line in enumerate(_split_lines(content), start=1):
            haystack = line.lower() if ignore_case else line

            if exact:
                matched = haystack == needle
            else:
                matched = needle in haystack

            if invert:
                matched = not matched

            if not matched:
                continue

            file_matched = True
            if names_only:
                continue

            prefix = []
            if multiple_files:
                prefix.append(fname)
            if show_number:
                prefix.append(str(number))

            if prefix:
                output.append(":".join(prefix) + ":" + line + "\n")
            else:
                output.append(line + "\n")

        if names_only and file_matched:
            output.append(fname + "\n")

    return "".join(output)
