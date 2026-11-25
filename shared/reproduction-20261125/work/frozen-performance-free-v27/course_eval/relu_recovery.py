import numpy as np


def _fit_plane(points):
    if points.shape[1] == 1:
        return np.ones(1), -float(np.median(points[:, 0]))
    center = points.mean(axis=0)
    _, singular, vectors = np.linalg.svd(points - center, full_matrices=False)
    if len(singular) < points.shape[1] or singular[-2] < 1e-6:
        raise RuntimeError("Critical witnesses do not span a hyperplane")
    normal = vectors[-1]
    normal /= np.linalg.norm(normal)
    return normal, -float(center @ normal)


def _refine_planes(query, rows, biases, dimension, seed):
    # 依据Carlini等CRYPTO2020第5.1/5.3节：重新定位临界点，再稳健拟合超平面。
    # https://arxiv.org/abs/2003.04884；不接收未知宽度或原权重。
    rng = np.random.default_rng(seed)
    refined, refined_biases, diagnostics = [], [], []
    required = 4 * dimension + 1
    for index, (normal, bias) in enumerate(zip(rows, biases)):
        points = []
        for _ in range(6 * required):
            point = rng.normal(size=dimension) * 2.0
            point -= (float(point @ normal) + bias) * normal
            for radius in (0.01, 0.003, 0.001):
                low, middle_low, middle_high, high = (
                    query(point + t * normal)
                    for t in (-radius, -radius / 2, radius / 2, radius)
                )
                left_slope = (middle_low - low) / (radius / 2)
                right_slope = (high - middle_high) / (radius / 2)
                jump = left_slope - right_slope
                if abs(jump) <= 1e-9 * (1 + abs(left_slope) + abs(right_slope)):
                    continue
                left_intercept = low + radius * left_slope
                right_intercept = high - radius * right_slope
                crossing = (right_intercept - left_intercept) / jump
                if abs(crossing) >= 0.45 * radius:
                    continue
                value = query(point + crossing * normal)
                predicted = left_intercept + crossing * left_slope
                tolerance = 2e-11 * (1 + abs(value) + abs(predicted))
                if abs(value - predicted) > tolerance:
                    continue
                checks = ((crossing - radius / 8, left_intercept, left_slope),
                          (crossing + radius / 8, right_intercept, right_slope))
                if any(abs(query(point + t * normal) - (intercept + slope * t)) > tolerance
                       for t, intercept, slope in checks):
                    continue
                points.append(point + crossing * normal)
                break
            if len(points) >= required:
                break
        if len(points) < required:
            raise RuntimeError(f"Insufficient isolated critical witnesses for direction {index}")
        points = np.asarray(points)
        fitted, offset = normal.copy(), bias
        retained = max(dimension + 4, int(np.ceil(0.75 * len(points))))
        for _ in range(8):
            residuals = np.abs(points @ fitted + offset)
            selected = np.argsort(residuals)[:retained]
            fitted, offset = _fit_plane(points[selected])
        residuals = np.abs(points @ fitted + offset)
        inliers = points[residuals <= max(1e-9, 5 * float(np.median(residuals)))]
        if len(inliers) < 2 * (dimension + 1):
            raise RuntimeError(f"Critical witnesses disagree for direction {index}")
        first, _ = _fit_plane(inliers[::2])
        second, _ = _fit_plane(inliers[1::2])
        disagreement = min(float(np.linalg.norm(first - second)),
                           float(np.linalg.norm(first + second)))
        if disagreement > 1e-7:
            raise RuntimeError(f"Independent critical-witness fits disagree for direction {index}")
        fitted, offset = _fit_plane(inliers)
        if abs(float(fitted @ normal)) < 0.999:
            raise RuntimeError(f"Precision refinement switched hyperplanes for direction {index}")
        if float(fitted @ normal) < 0:
            fitted, offset = -fitted, -offset
        refined.append(fitted)
        refined_biases.append(offset)
        diagnostics.append({"witnesses": len(points), "inliers": len(inliers),
                            "split_direction_disagreement": disagreement,
                            "max_inlier_residual": float(np.max(np.abs(inliers @ fitted + offset)))})
    return np.stack(refined), np.asarray(refined_biases), diagnostics


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
    directions, offsets = [], []
    for _ in range(n_lines):
        origin = rng.normal(size=dimension)
        direction = rng.normal(size=dimension)
        direction /= np.linalg.norm(direction)
        values = np.array([query(origin + time * direction) for time in times])
        slopes = np.diff(values) / t_step
        tolerance = 1e-7 + 1e-6 * float(np.max(np.abs(slopes)))
        boundaries = [0, *[index for index in range(1, len(slopes))
                          if abs(slopes[index] - slopes[index - 1]) > tolerance], len(slopes)]
        points = [origin + 0.5 * (times[left] + times[right]) * direction
                  for left, right in zip(boundaries[:-1], boundaries[1:])]
        gradients = [gradient(point) for point in points]
        intercepts = [query(point) - float(vector @ point)
                      for point, vector in zip(points, gradients)]
        # 跨越单个ReLU折点时，梯度差与对应权重行平行；不要求恢复其符号。
        for before, after, bias_before, bias_after in zip(
                gradients[:-1], gradients[1:], intercepts[:-1], intercepts[1:]):
            difference = after - before
            norm = float(np.linalg.norm(difference))
            if norm > 1e-6:
                directions.append(difference / norm)
                offsets.append((bias_after - bias_before) / norm)

    representatives, members, member_offsets = [], [], []
    for direction, offset in zip(directions, offsets):
        similarities = [abs(float(direction @ row)) for row in representatives]
        best = int(np.argmax(similarities)) if similarities else None
        if best is not None and similarities[best] > 0.999:
            sign = 1 if float(direction @ representatives[best]) >= 0 else -1
            members[best].append(sign * direction)
            member_offsets[best].append(sign * offset)
        else:
            representatives.append(direction.copy())
            members.append([direction.copy()])
            member_offsets.append([offset])
    counts = [len(group) for group in members]
    if not counts:
        raise RuntimeError("No nonzero ReLU gradient changes were observed")
    required_support = max(2, min(3, max(counts) // 4))
    rows, biases = [], []
    for group, bias_group, count in zip(members, member_offsets, counts):
        if count < required_support:
            continue
        row = np.median(np.asarray(group), axis=0)
        norm = float(np.linalg.norm(row))
        rows.append(row / norm)
        biases.append(float(np.median(bias_group)) / norm)
    if not rows:
        raise RuntimeError("No direction was supported by repeated observations")
    rows, _, precision = _refine_planes(query, np.stack(rows), np.asarray(biases), dimension, seed + 1)
    return rows, {"oracle_queries": calls, "probe_lines": n_lines,
                           "raw_directions": len(directions), "recovered_directions": len(rows),
                           "unknown_width_assumed": False, "sign_ambiguous": True,
                           "completeness_certified": False,
                           "precision_method": "Relocated critical witnesses and trimmed hyperplane SVD; Carlini et al. CRYPTO2020 sections 5.1/5.3",
                           "precision": precision,
                           "limitations": "Finite grids and support filtering can miss close or weak kinks"}


def validate_saved_directions(oracle, dimension, actual, *, tolerance=1e-6):
    actual = np.asarray(actual)
    if (actual.ndim != 2 or actual.shape[1] != dimension or not len(actual)
            or not np.isfinite(actual).all() or np.any(np.linalg.norm(actual, axis=1) == 0)):
        raise ValueError("The delivered weight matrix is not a finite nonzero-row matrix")
    reference, diagnostics = recover_relu_directions(oracle, dimension, n_lines=23, seed=39117)
    actual = actual / np.linalg.norm(actual, axis=1, keepdims=True)
    cosine = reference @ actual.T
    match = np.argmax(np.abs(cosine), axis=1)
    errors = [float(np.linalg.norm(row - (1 if cosine[index, column] >= 0 else -1) * actual[column]))
              for index, (row, column) in enumerate(zip(reference, match))]
    one_to_one = len(set(int(column) for column in match)) == len(reference) == len(actual)
    return {"passed": one_to_one and max(errors) <= tolerance,
            "actual_shape": list(actual.shape), "query_inferred_shape": list(reference.shape),
            "one_to_one": one_to_one, "max_direction_error": max(errors),
            "direction_tolerance": tolerance, "fresh_oracle_queries": diagnostics["oracle_queries"],
            "completeness_certified": False,
            "scope": "Fresh-query numerical consistency; finite probing cannot certify all hidden units"}


