def grep(pattern, flags, files):
    if isinstance(flags, str):
        flag_set = set(flags.split())
    else:
        flag_set = set(flags)

    show_line_numbers = "-n" in flag_set
    show_file_names = "-l" in flag_set
    ignore_case = "-i" in flag_set
    invert = "-v" in flag_set
    exact = "-x" in flag_set

    needle = pattern.lower() if ignore_case else pattern
    multiple_files = len(files) > 1
    results = []

    for filename in files:
        with open(filename) as file:
            lines = file.read().splitlines()

        for line_number, line in enumerate(lines, 1):
            candidate = line.lower() if ignore_case else line
            matched = candidate == needle if exact else needle in candidate
            if invert:
                matched = not matched
            if not matched:
                continue

            if show_file_names:
                results.append(filename + "\n")
                break

            prefix = []
            if multiple_files:
                prefix.append(filename)
            if show_line_numbers:
                prefix.append(str(line_number))
            prefix.append(line)
            results.append(":".join(prefix) + "\n")

    return "".join(results)
