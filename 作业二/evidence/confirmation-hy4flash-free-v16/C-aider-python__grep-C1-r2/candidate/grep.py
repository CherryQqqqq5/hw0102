def grep(pattern, flags, files):
    flags = set(flags.split())
    case_insensitive = "-i" in flags
    invert = "-v" in flags
    exact = "-x" in flags
    line_numbers = "-n" in flags
    names_only = "-l" in flags
    multiple_files = len(files) > 1

    needle = pattern.casefold() if case_insensitive else pattern
    results = []

    for filename in files:
        with open(filename) as file:
            lines = file.read().splitlines()

        file_has_match = False
        for line_no, line in enumerate(lines, 1):
            haystack = line.casefold() if case_insensitive else line
            matches = haystack == needle if exact else needle in haystack
            if invert:
                matches = not matches

            if not matches:
                continue

            if names_only:
                file_has_match = True
                break

            prefix = ""
            if multiple_files:
                prefix = f"{filename}:"
            if line_numbers:
                prefix += f"{line_no}:"
            results.append(f"{prefix}{line}\n")

        if names_only and file_has_match:
            results.append(f"{filename}\n")

    return "".join(results)
