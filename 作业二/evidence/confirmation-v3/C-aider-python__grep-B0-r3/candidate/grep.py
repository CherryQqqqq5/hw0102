def grep(pattern, flags, files):
    flag_set = set(flags.split())
    show_line_numbers = "-n" in flag_set
    show_only_names = "-l" in flag_set
    case_insensitive = "-i" in flag_set
    invert = "-v" in flag_set
    match_whole_line = "-x" in flag_set

    needle = pattern.lower() if case_insensitive else pattern
    multiple_files = len(files) > 1
    output = []

    for filename in files:
        with open(filename) as f:
            lines = f.read().splitlines()

        matched = []
        for index, line in enumerate(lines, start=1):
            haystack = line.lower() if case_insensitive else line
            if match_whole_line:
                found = haystack == needle
            else:
                found = needle in haystack
            if invert:
                found = not found
            if found:
                matched.append((index, line))

        if not matched:
            continue

        if show_only_names:
            output.append(filename + "\n")
            continue

        for index, line in matched:
            prefix = ""
            if multiple_files:
                prefix += filename + ":"
            if show_line_numbers:
                prefix += str(index) + ":"
            output.append(prefix + line + "\n")

    return "".join(output)
