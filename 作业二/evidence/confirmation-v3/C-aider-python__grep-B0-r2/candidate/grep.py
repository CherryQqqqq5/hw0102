def grep(pattern, flags, files):
    """Search files for lines matching the fixed string `pattern`.

    Supports the flags -n, -l, -i, -v and -x.
    """
    flag_set = set(flags.split())
    show_line_numbers = "-n" in flag_set
    files_only = "-l" in flag_set
    ignore_case = "-i" in flag_set
    invert_match = "-v" in flag_set
    whole_line = "-x" in flag_set

    if ignore_case:
        needle = pattern.lower()
    else:
        needle = pattern

    many_files = len(files) > 1
    result = []

    for filename in files:
        with open(filename) as f:
            lines = f.read().splitlines()

        file_matched = False
        output = []

        for line_number, line in enumerate(lines, start=1):
            haystack = line.lower() if ignore_case else line

            if whole_line:
                matched = haystack == needle
            else:
                matched = needle in haystack

            if invert_match:
                matched = not matched

            if not matched:
                continue

            file_matched = True

            if files_only:
                # Only file names are wanted; no need to build line output.
                break

            prefix = ""
            if many_files:
                prefix += filename + ":"
            if show_line_numbers:
                prefix += str(line_number) + ":"
            output.append(prefix + line + "\n")

        if files_only:
            if file_matched:
                result.append(filename + "\n")
        else:
            result.extend(output)

    return "".join(result)
