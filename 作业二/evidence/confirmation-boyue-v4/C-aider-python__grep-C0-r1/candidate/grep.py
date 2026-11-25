def grep(pattern, flags, files):
    """Search *files* for lines containing the fixed string *pattern*.

    Supported flags:
        -n  Prepend the 1-based line number.
        -l  Output only the names of files that contain a match.
        -i  Match using a case-insensitive comparison.
        -v  Invert the match (keep non-matching lines).
        -x  Require the pattern to match the whole line.
    """
    # Flags are normally supplied as a string (e.g. "-n -i"), but keep this
    # tolerant of combined forms such as "-ni" as well.
    flag_chars = set("".join(flags).replace("-", "").replace(" ", ""))

    show_line_numbers = "n" in flag_chars
    list_file_names = "l" in flag_chars
    case_insensitive = "i" in flag_chars
    invert_match = "v" in flag_chars
    whole_line = "x" in flag_chars

    haystack_pattern = pattern.lower() if case_insensitive else pattern
    prefix_file_names = len(files) > 1
    output_parts = []
    file_names_with_match = []

    for file_name in files:
        with open(file_name, encoding="utf-8") as source:
            if list_file_names:
                # Once any matching line is found, do not read further.
                for raw_line in source:
                    if _matches(
                        _strip_line_ending(raw_line),
                        haystack_pattern,
                        case_insensitive,
                        whole_line,
                    ) != invert_match:
                        file_names_with_match.append(file_name)
                        break
                continue

            for line_number, raw_line in enumerate(source, start=1):
                matches = _matches(
                    _strip_line_ending(raw_line),
                    haystack_pattern,
                    case_insensitive,
                    whole_line,
                )
                if matches == invert_match:
                    continue

                line = raw_line
                if not line.endswith("\n"):
                    line += "\n"

                prefixes = []
                if prefix_file_names:
                    prefixes.append(file_name)
                if show_line_numbers:
                    prefixes.append(str(line_number))

                if prefixes:
                    output_parts.append(":".join(prefixes) + ":" + line)
                else:
                    output_parts.append(line)

    if list_file_names:
        return "".join(name + "\n" for name in file_names_with_match)

    return "".join(output_parts)


def _strip_line_ending(line):
    """Remove a single trailing newline (and optional carriage return)."""
    if line.endswith("\n"):
        line = line[:-1]
    if line.endswith("\r"):
        line = line[:-1]
    return line


def _matches(line, pattern, case_insensitive, whole_line):
    line_for_match = line.lower() if case_insensitive else line
    if whole_line:
        return line_for_match == pattern
    return pattern in line_for_match
