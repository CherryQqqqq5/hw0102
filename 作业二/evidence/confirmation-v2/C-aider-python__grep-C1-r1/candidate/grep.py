def grep(pattern, flags, files):
    flag_set = set(flags.split())

    show_line_numbers = "-n" in flag_set
    files_only = "-l" in flag_set
    ignore_case = "-i" in flag_set
    invert = "-v" in flag_set
    entire_line = "-x" in flag_set

    if ignore_case:
        pattern = pattern.lower()

    multiple_files = len(files) > 1

    results = []
    for filename in files:
        with open(filename) as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                line = raw_line.rstrip("\n")
                comparable = line.lower() if ignore_case else line
                if entire_line:
                    matched = comparable == pattern
                else:
                    matched = pattern in comparable
                if invert:
                    matched = not matched
                if not matched:
                    continue
                if files_only:
                    results.append(filename + "\n")
                    break
                prefix = ""
                if multiple_files:
                    prefix += filename + ":"
                if show_line_numbers:
                    prefix += str(line_number) + ":"
                results.append(prefix + line + "\n")

    return "".join(results)
