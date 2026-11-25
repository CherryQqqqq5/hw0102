import numpy as np


def recover_relu_directions(oracle, dimension, *, n_lines=15, t_range=10.0,
                            t_step=0.004, gradient_step=1e-6, seed=20240517):
    if type(dimension) is not int or dimension < 1 or type(n_lines) is not int or n_lines < 3:
        raise ValueError("A positive input dimension and at least three probe lines are required")
    if not all(np.isfinite(value) and value > 0 for value in (t_range, t_step, gradient_step)):
        raise ValueError("Probe scales must be positive finite numbers")
    calls = 0

    def query(point):
        nonlocal calls
        calls += 1
        result = float(oracle(np.asarray(point, dtype=float)))
        if not np.isfinite(result):
            raise ValueError("The scalar oracle returned a non-finite value")
        return result

    def gradient(point):
        result = np.empty(dimension)
        for index in range(dimension):
            offset = np.zeros(dimension)
            offset[index] = gradient_step
            result[index] = (query(point + offset) - query(point - offset)) / (2 * gradient_step)
        return result

    rng = np.random.default_rng(seed)
    times = np.arange(-t_range, t_range + 1e-12, t_step)
    if len(times) < 3:
        raise ValueError("The probe grid must have at least three points")
    directions = []
    for _ in range(n_lines):
        origin = rng.normal(size=dimension)
        direction = rng.normal(size=dimension)
        direction /= np.linalg.norm(direction)
        values = np.array([query(origin + time * direction) for time in times])
        slopes = np.diff(values) / t_step
        tolerance = 1e-7 + 1e-6 * float(np.max(np.abs(slopes)))
        boundaries = [0, *[index for index in range(1, len(slopes))
                          if abs(slopes[index] - slopes[index - 1]) > tolerance], len(slopes)]
        gradients = [gradient(origin + 0.5 * (times[left] + times[right]) * direction)
                     for left, right in zip(boundaries[:-1], boundaries[1:])]
        # 跨越单个ReLU折点时，梯度差与对应权重行平行；不要求恢复其符号。
        for before, after in zip(gradients[:-1], gradients[1:]):
            difference = after - before
            norm = float(np.linalg.norm(difference))
            if norm > 1e-6:
                directions.append(difference / norm)

    representatives, sums, counts = [], [], []
    for direction in directions:
        similarities = [abs(float(direction @ row)) for row in representatives]
        best = int(np.argmax(similarities)) if similarities else None
        if best is not None and similarities[best] > 0.999:
            sign = 1 if float(direction @ representatives[best]) >= 0 else -1
            sums[best] += sign * direction
            counts[best] += 1
        else:
            representatives.append(direction.copy())
            sums.append(direction.copy())
            counts.append(1)
    if not counts:
        raise RuntimeError("No nonzero ReLU gradient changes were observed")
    required_support = max(2, min(3, max(counts) // 4))
    rows = [row / np.linalg.norm(row) for row, count in zip(sums, counts) if count >= required_support]
    if not rows:
        raise RuntimeError("No direction was supported by repeated observations")
    return np.stack(rows), {"oracle_queries": calls, "probe_lines": n_lines,
                           "raw_directions": len(directions), "recovered_directions": len(rows),
                           "unknown_width_assumed": False, "sign_ambiguous": True,
                           "completeness_certified": False,
                           "limitations": "Finite grids and support filtering can miss close or weak kinks"}
