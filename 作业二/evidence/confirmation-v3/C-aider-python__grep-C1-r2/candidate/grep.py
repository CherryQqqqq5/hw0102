def grep(pattern, flags, files):
    flag_set = set(flags.split())
    case_insensitive = "-i" in flag_set
    invert = "-v" in flag_set
    entire_line = "-x" in flag_set
    show_line_numbers = "-n" in flag_set
    files_only = "-l" in flag_set

    needle = pattern.lower() if case_insensitive else pattern
    multiple_files = len(files) > 1
    output = []

    for filename in files:
        matched_any = False
        with open(filename) as f:
            for index, line in enumerate(f, start=1):
                line = line.rstrip("\n")
                haystack = line.lower() if case_insensitive else line
                if entire_line:
                    matched = haystack == needle
                else:
                    matched = needle in haystack
                if invert:
                    matched = not matched
                if not matched:
                    continue
                matched_any = True
                if not files_only:
                    prefix = ""
                    if multiple_files:
                        prefix += filename + ":"
                    if show_line_numbers:
                        prefix += str(index) + ":"
                    output.append(prefix + line)
        if files_only and matched_any:
            output.append(filename)

    return "".join(line + "\n" for line in output)
