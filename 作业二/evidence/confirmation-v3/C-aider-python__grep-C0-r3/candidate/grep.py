def grep(pattern, flags, files):
    flag_set = set()
    for flag in flags.split():
        if flag.startswith("-"):
            flag_set.update(flag[1:])
        else:
            flag_set.update(flag)

    line_numbers = "n" in flag_set
    only_names = "l" in flag_set
    ignore_case = "i" in flag_set
    invert = "v" in flag_set
    entire_line = "x" in flag_set

    needle = pattern.lower() if ignore_case else pattern
    multiple = len(files) > 1

    output = []

    for filename in files:
        matched_any = False
        with open(filename) as handle:
            content = handle.read()

        # Normalise line endings and drop the trailing empty element that a
        # final newline would otherwise produce.
        lines = content.splitlines()

        for number, line in enumerate(lines, start=1):
            haystack = line.lower() if ignore_case else line

            if entire_line:
                matched = haystack == needle
            else:
                matched = needle in haystack

            if invert:
                matched = not matched

            if not matched:
                continue

            matched_any = True

            if only_names:
                continue

            parts = []
            if multiple:
                parts.append(filename + ":")
            if line_numbers:
                parts.append(str(number) + ":")
            parts.append(line)

            output.append("".join(parts))

        if only_names and matched_any:
            output.append(filename)

    return "".join(item + "\n" for item in output)
