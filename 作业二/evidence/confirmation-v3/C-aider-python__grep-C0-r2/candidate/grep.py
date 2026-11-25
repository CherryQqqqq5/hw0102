def grep(pattern, flags, files):
    """Simplified grep supporting fixed-string search with -n -l -i -v -x."""
    flag_set = set()
    for flag in (flags or "").split():
        if flag.startswith("-") and len(flag) > 1:
            flag_set.update(flag[1:])
        elif flag:
            flag_set.add(flag)

    invert = "v" in flag_set
    ignore_case = "i" in flag_set
    exact = "x" in flag_set
    show_line_numbers = "n" in flag_set
    names_only = "l" in flag_set

    multiple_files = len(files) > 1
    needle = pattern.lower() if ignore_case else pattern
    output = []

    for filename in files:
        matched = False
        with open(filename) as handle:
            for number, line in enumerate(handle.read().splitlines(), start=1):
                haystack = line.lower() if ignore_case else line
                is_match = (haystack == needle) if exact else (needle in haystack)
                if is_match != invert:
                    matched = True
                    if names_only:
                        continue
                    prefix = ""
                    if multiple_files:
                        prefix += filename + ":"
                    if show_line_numbers:
                        prefix += str(number) + ":"
                    output.append(prefix + line + "\n")
        if names_only and matched:
            output.append(filename + "\n")

    return "".join(output)
