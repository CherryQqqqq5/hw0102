def grep(pattern, flags, files):
    flag_set = set()
    for flag in flags.split():
        if flag.startswith('-'):
            flag = flag[1:]
        flag_set.update(flag)

    ignore_case = 'i' in flag_set
    line_numbers = 'n' in flag_set
    names_only = 'l' in flag_set
    invert = 'v' in flag_set
    exact = 'x' in flag_set

    needle = pattern.casefold() if ignore_case else pattern
    multiple_files = len(files) > 1
    output = []

    for filename in files:
        file_has_match = False
        with open(filename) as handle:
            for number, raw_line in enumerate(handle, 1):
                line = raw_line.rstrip('\r\n')
                candidate = line.casefold() if ignore_case else line

                if exact:
                    is_match = candidate == needle
                else:
                    is_match = needle in candidate

                if invert:
                    is_match = not is_match

                if not is_match:
                    continue

                file_has_match = True
                if names_only:
                    break

                prefix = ''
                if multiple_files:
                    prefix += filename + ':'
                if line_numbers:
                    prefix += str(number) + ':'
                output.append(prefix + line + '\n')

        if names_only and file_has_match:
            output.append(filename + '\n')

    return ''.join(output)
