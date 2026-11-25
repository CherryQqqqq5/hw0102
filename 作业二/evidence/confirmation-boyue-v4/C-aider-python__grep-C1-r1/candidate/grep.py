def grep(pattern, flags, files):
    """Search files for lines containing ``pattern`` and return matches.

    Supported flags are:

    - ``-n``: prepend the line number (followed by ``:``) to each result.
    - ``-l``: print only the names of files that contain at least one match.
    - ``-i``: perform a case-insensitive comparison.
    - ``-v``: invert the match, collecting lines that do not match.
    - ``-x``: match only lines where ``pattern`` matches the entire line.

    Results keep the original line content (including any trailing newline)
    and files are searched in the order supplied.
    """
    flag_chars = set(flags.replace("-", "").replace(" ", ""))

    line_numbers = "n" in flag_chars
    filenames_only = "l" in flag_chars
    ignore_case = "i" in flag_chars
    invert = "v" in flag_chars
    whole_line = "x" in flag_chars

    multiple_files = len(files) > 1
    needle = pattern.lower() if ignore_case else pattern

    results = []

    for filename in files:
        with open(filename, encoding="utf-8") as handle:
            lines = handle.readlines()

        if filenames_only:
            for line in lines:
                content = line.rstrip("\r\n")
                haystack = content.lower() if ignore_case else content
                matched = (
                    haystack == needle if whole_line else needle in haystack
                )
                if invert:
                    matched = not matched
                if matched:
                    results.append(filename + "\n")
                    break
            continue

        for number, line in enumerate(lines, start=1):
            content = line.rstrip("\r\n")
            haystack = content.lower() if ignore_case else content
            matched = haystack == needle if whole_line else needle in haystack
            if invert:
                matched = not matched

            if matched:
                prefix = ""
                if multiple_files:
                    prefix += filename + ":"
                if line_numbers:
                    prefix += str(number) + ":"
                results.append(prefix + line)

    return "".join(results)
