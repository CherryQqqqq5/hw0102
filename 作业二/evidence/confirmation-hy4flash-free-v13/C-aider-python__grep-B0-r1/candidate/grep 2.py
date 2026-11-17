def grep(pattern, flags, files):
    """Search files for fixed-string matches and return formatted output."""
    flag_set = set(flags.split()) if isinstance(flags, str) else set(flags)
    ignore_case = "-i" in flag_set
    line_numbers = "-n" in flag_set
    filenames_only = "-l" in flag_set
    invert = "-v" in flag_set
    exact = "-x" in flag_set

    needle = pattern.lower() if ignore_case else pattern
    files = list(files)
    show_filenames = len(files) > 1
    output = []

    for filename in files:
        file_reported = False
        with open(filename) as current_file:
            for line_number, raw_line in enumerate(current_file, start=1):
                line = raw_line[:-1] if raw_line.endswith("\n") else raw_line
                if line.endswith("\r"):
                    line = line[:-1]

                candidate = line.lower() if ignore_case else line
                matches = candidate == needle if exact else needle in candidate
                selected = not matches if invert else matches

                if not selected:
                    continue

                if filenames_only:
                    if not file_reported:
                        output.append(filename + "\n")
                        file_reported = True
                    continue

                prefix = ""
                if show_filenames:
                    prefix += filename + ":"
                if line_numbers:
                    prefix += str(line_number) + ":"
                output.append(prefix + line + "\n")

    return "".join(output)
