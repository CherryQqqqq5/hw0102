def grep(pattern, flags, files):
    """Search files for lines containing pattern and return matching lines."""
    flag_list = []
    for token in flags.split():
        if token.startswith("-") and len(token) > 2:
            flag_list.extend("-" + ch for ch in token[1:])
        else:
            flag_list.append(token)
    line_numbers = "-n" in flag_list
    names_only = "-l" in flag_list
    ignore_case = "-i" in flag_list
    invert = "-v" in flag_list
    exact_line = "-x" in flag_list

    multiple_files = len(files) > 1
    needle = pattern.lower() if ignore_case else pattern

    output = []

    for filename in files:
        with open(filename, "r") as handle:
            content = handle.read()

        if content == "":
            lines = []
        else:
            lines = content.split("\n")
            if lines and lines[-1] == "":
                lines.pop()

        file_matched = False
        for number, line in enumerate(lines, start=1):
            haystack = line.lower() if ignore_case else line
            matched = haystack == needle if exact_line else needle in haystack
            if invert:
                matched = not matched
            if not matched:
                continue

            file_matched = True
            if names_only:
                break

            prefix = ""
            if multiple_files:
                prefix += filename + ":"
            if line_numbers:
                prefix += str(number) + ":"
            output.append(prefix + line + "\n")

        if names_only and file_matched:
            output.append(filename + "\n")

    return "".join(output)
