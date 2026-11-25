import json
import sys

import cv2
import numpy as np


def read_video(path):
    capture = cv2.VideoCapture(path)
    frames = []
    try:
        while True:
            valid, frame = capture.read()
            if not valid:
                break
            frames.append(frame)
    finally:
        capture.release()
    if not frames:
        raise ValueError("No readable video frames: " + str(path))
    return frames


def build_background(frames):
    if len(frames) > 180:
        indices = np.linspace(0, len(frames) - 1, 180).astype(int)
        sample = [frames[index] for index in indices]
    else:
        sample = frames
    return np.median(np.stack(sample), axis=0).astype(np.uint8)


def athlete_geometry(frame, background, kernel, min_area):
    height, _ = frame.shape[:2]
    difference = np.max(np.abs(frame.astype(np.int16) - background.astype(np.int16)), axis=2)
    mask = (difference > 40).astype(np.uint8)
    mask[:int(0.28 * height), :] = 0
    mask[int(0.80 * height):, :] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    count, _, statistics, _ = cv2.connectedComponentsWithStats(mask, 8)
    candidates = [index for index in range(1, count) if statistics[index, cv2.CC_STAT_AREA] >= min_area]
    if not candidates:
        return None, None
    main = max(candidates, key=lambda index: statistics[index, cv2.CC_STAT_AREA])
    x = int(statistics[main, cv2.CC_STAT_LEFT])
    y = int(statistics[main, cv2.CC_STAT_TOP])
    width = int(statistics[main, cv2.CC_STAT_WIDTH])
    height = int(statistics[main, cv2.CC_STAT_HEIGHT])
    bottom = y + height - 1
    left, right = x, x + width - 1
    midpoint = (left + right) / 2.0
    # 着地脚可能与身体断开，仍需把相邻脚部计入最低点。
    for index in range(1, count):
        if index == main or statistics[index, cv2.CC_STAT_AREA] < 80:
            continue
        other_x = int(statistics[index, cv2.CC_STAT_LEFT])
        other_y = int(statistics[index, cv2.CC_STAT_TOP])
        other_width = int(statistics[index, cv2.CC_STAT_WIDTH])
        other_height = int(statistics[index, cv2.CC_STAT_HEIGHT])
        nearby_x = other_x <= right + 80 and other_x + other_width - 1 >= left - 80
        if nearby_x and other_y <= bottom + 25:
            bottom = max(bottom, other_y + other_height - 1)
    return bottom, midpoint


def moving_span(midpoints, valid, min_length=6):
    best = None
    for direction in (-1, 1):
        start = None
        for index in range(len(midpoints) - 1):
            delta = midpoints[index + 1] - midpoints[index]
            moving = valid[index] and valid[index + 1] and direction * delta > 2.0
            if moving:
                if start is None:
                    start = index
            elif start is not None:
                span = (start, index)
                if span[1] - span[0] + 1 >= min_length:
                    if best is None or span[1] - span[0] > best[1] - best[0]:
                        best = span
                start = None
        if start is not None:
            span = (start, len(midpoints) - 1)
            if span[1] - span[0] + 1 >= min_length:
                if best is None or span[1] - span[0] > best[1] - best[0]:
                    best = span
    return best


def longest_flight(bottoms, valid, height):
    values = bottoms[valid]
    if len(values) < 5:
        raise ValueError("Too few usable athlete positions to identify a jump")
    ground = float(np.percentile(values, 90))
    threshold = ground - max(10.0, 0.02 * height)
    airborne = valid & (bottoms < threshold)
    runs = []
    start = None
    for index, is_airborne in enumerate(airborne):
        if is_airborne:
            if start is None:
                start = index
        elif start is not None:
            runs.append((start, index - 1))
            start = None
    if start is not None:
        runs.append((start, len(airborne) - 1))
    runs = [(start, end) for start, end in runs if end - start + 1 >= 3]
    if not runs:
        raise ValueError("No sustained airborne interval was detected")

    def score(run):
        start, end = run
        return float(np.mean(ground - bottoms[start:end + 1])) * (end - start + 1)

    return max(runs, key=score), ground, threshold


def analyze_video(path):
    frames = read_video(path)
    count = len(frames)
    height, width = frames[0].shape[:2]
    background = build_background(frames)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    min_area = max(300, int(0.003 * width * height))
    bottoms = np.full(count, np.nan, dtype=float)
    midpoints = np.full(count, np.nan, dtype=float)
    for index, frame in enumerate(frames):
        bottom, midpoint = athlete_geometry(frame, background, kernel, min_area)
        if bottom is not None:
            bottoms[index] = bottom
            midpoints[index] = midpoint
    valid = ~np.isnan(bottoms)
    span = moving_span(midpoints, valid)
    if span is not None:
        keep = np.zeros(count, dtype=bool)
        keep[span[0]:span[1] + 1] = True
        valid &= keep
        bottoms[~keep] = np.nan
    (start, end), ground, threshold = longest_flight(bottoms, valid, height)
    takeoff, landing = start - 1, end + 1
    if (takeoff < 0 or landing >= count or not valid[takeoff] or not valid[landing]
            or bottoms[takeoff] < threshold or bottoms[landing] < threshold):
        raise ValueError("The jump lacks adjacent observable ground-contact boundaries")
    return {"takeoff_frame": int(takeoff), "landing_frame": int(landing),
        "frame_count": count, "ground_y": ground, "airborne_threshold_y": threshold,
        "motion_span": list(span) if span is not None else None,
        "scope": "Fixed-camera single-runner heuristic; event indices are inferred from input pixels"}


if __name__ == "__main__":
    print(json.dumps(analyze_video(sys.argv[1])))
