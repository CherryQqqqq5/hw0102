def proverb(*pieces, qualifier=None):
    if not pieces:
        return []

    lines = [
        f"For want of a {pieces[i]} the {pieces[i + 1]} was lost."
        for i in range(len(pieces) - 1)
    ]
    prefix = f"{qualifier} " if qualifier else ""
    lines.append(f"And all for the want of a {prefix}{pieces[0]}.")
    return lines
