def grep(pattern, flags, files):
    flag_set = set(flags.split())

    case_insensitive = "-i" in flag_set
    invert = "-v" in flag_set
    entire_line = "-x" in flag_set
    show_line_numbers = "-n" in flag_set
    show_only_filenames = "-l" in flag_set

    needle = pattern.lower() if case_insensitive else pattern

    output = []
    for filename in files:
        with open(filename) as f:
            lines = f.read().splitlines()

        matched_file = False
        for number, line in enumerate(lines, start=1):
            haystack = line.lower() if case_insensitive else line
            if entire_line:
                matched = haystack == needle
            else:
                matched = needle in haystack
            if invert:
                matched = not matched

            if not matched:
                continue

            matched_file = True
            if show_only_filenames:
                continue

            prefix = ""
            if len(files) > 1:
                prefix += filename + ":"
            if show_line_numbers:
                prefix += str(number) + ":"
            output.append(prefix + line + "\n")

        if show_only_filenames and matched_file:
            output.append(filename + "\n")

    return "".join(output)
