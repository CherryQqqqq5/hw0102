def grep(pattern, flags, files):
    """Return lines from ``files`` that contain the fixed string ``pattern``."""
    if not flags:
        flag_tokens = []
    elif isinstance(flags, str):
        flag_tokens = flags.split()
    else:
        flag_tokens = list(flags)

    flag_set = set()
    for flag in flag_tokens:
        flag_set.add(flag)
        # Accept combined short flags such as "-ni" as a convenience.
        if flag.startswith("-") and not flag.startswith("--") and len(flag) > 2:
            flag_set.update("-" + char for char in flag[1:])

    ignore_case = "-i" in flag_set
    invert = "-v" in flag_set
    whole_line = "-x" in flag_set
    list_files = "-l" in flag_set
    line_numbers = "-n" in flag_set

    files = list(files)
    prefix_files = len(files) > 1
    needle = pattern.lower() if ignore_case else pattern
    result = []

    for file_name in files:
        with open(file_name) as file:
            contents = file.read()

        lines = contents.split("\n")
        if lines and lines[-1] == "":
            lines.pop()

        file_has_match = False
        for line_number, line in enumerate(lines, 1):
            comparable_line = line.lower() if ignore_case else line
            if whole_line:
                matched = comparable_line == needle
            else:
                matched = needle in comparable_line

            if invert:
                matched = not matched

            if not matched:
                continue

            if list_files:
                file_has_match = True
                break

            prefix = ""
            if prefix_files:
                prefix += file_name + ":"
            if line_numbers:
                prefix += str(line_number) + ":"
            result.append(prefix + line + "\n")

        if list_files and file_has_match:
            result.append(file_name + "\n")

    return "".join(result)
