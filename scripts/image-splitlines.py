"""Takes an input image (PNG) and creates a separate image for each line of text."""

# Ref:
# - https://stackoverflow.com/a/48268334
# - https://www.geeksforgeeks.org/python/dividing-images-into-equal-parts-using-opencv-in-python/

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np


def segment_lines_by_components(inv, min_height_frac=0.5, max_height_frac=2.5):
    """
    inv: binary image, text=nonzero, background=0 (e.g. your `inv` from absdiff)
    Returns: list of (top, bottom) y-ranges, one per detected text line, sorted top-to-bottom.
    """
    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(inv, connectivity=8)

    boxes = []
    for i in range(1, n_labels):  # skip label 0 (background)
        x, y, w, h, area = stats[i]
        if area < 2:  # drop single-pixel noise
            continue
        boxes.append((x, y, w, h))

    heights = np.array([h for (x, y, w, h) in boxes])
    median_h = np.median(heights)

    core, small, noise = [], [], []
    for b in boxes:
        x, y, w, h = b
        if h > max_height_frac * median_h:
            noise.append(b)          # too tall to be a single glyph — border, rule line, artifact
        elif h < min_height_frac * median_h:
            small.append(b)          # diacritic-sized
        else:
            core.append(b)

    # --- Step 1: cluster core blobs into lines by y-overlap ---
    core_sorted = sorted(core, key=lambda b: b[1])
    lines = []
    for (x, y, w, h) in core_sorted:
        top, bottom = y, y + h
        placed = False
        for line in lines:
            if top <= line['bottom'] and bottom >= line['top']:
                line['top'] = min(line['top'], top)
                line['bottom'] = max(line['bottom'], bottom)
                line['boxes'].append((x, y, w, h))
                placed = True
                break
        if not placed:
            lines.append({'top': top, 'bottom': bottom, 'boxes': [(x, y, w, h)]})

    # re-pass merge, in case updates created new overlaps
    lines.sort(key=lambda l: l['top'])
    merged = []
    for line in lines:
        if merged and line['top'] <= merged[-1]['bottom']:
            merged[-1]['bottom'] = max(merged[-1]['bottom'], line['bottom'])
            merged[-1]['boxes'].extend(line['boxes'])
        else:
            merged.append(line)
    lines = merged

    # --- Step 2: assign diacritic blobs to nearest line by x-overlap ---
    for (x, y, w, h) in small:
        bx0, bx1 = x, x + w
        best_line, best_gap = None, None
        for line in lines:
            overlaps_x = any(not (bx1 < lx or bx0 > lx + lw) for (lx, ly, lw, lh) in line['boxes'])
            if not overlaps_x:
                continue
            gap = line['top'] - (y + h)  # positive: diacritic sits above this line
            if gap > -5 and (best_gap is None or abs(gap) < abs(best_gap)):
                best_gap, best_line = gap, line
        if best_line is not None:
            best_line['top'] = min(best_line['top'], y)
            best_line['bottom'] = max(best_line['bottom'], y + h)
            best_line['boxes'].append((x, y, w, h))
        else:
            lines.append({'top': y, 'bottom': y + h, 'boxes': [(x, y, w, h)]})  # rare fallback

    lines.sort(key=lambda l: l['top'])
    return [(l['top'], l['bottom']) for l in lines]


def segment_lines_by_whitespace(inv, min_gap_for_split=None):
    """
    Segment text lines using row-wise whitespace runs, distinguishing
    diacritic-to-base-letter gaps from real inter-line gaps.

    inv: binary image, text=nonzero (255), background=0 (e.g. your `inv` array)
    min_gap_for_split: optional override; if None, it's derived automatically
                        from the natural split in observed gap lengths.

    Returns: list of (top, bottom) row ranges, one per detected text line,
                sorted top-to-bottom.
    """
    # row is "text" if it has any foreground pixel at all
    cv2.imwrite("inv.png", inv)
    row_has_text = np.any(inv > 0, axis=1)
    # print(f"{row_has_text=}")
    text_rows = np.where(row_has_text)[0]
    # print(f"{text_rows=}")
    if len(text_rows) == 0:
        return []

    # trim to the actual content range, ignoring page margins
    first_row, last_row = text_rows[0], text_rows[-1]

    # find runs of all-zero rows (gaps) strictly within the content range
    gaps = []  # list of (start, end) row ranges that are blank
    in_gap = False
    gap_start = None
    for y in range(first_row, last_row + 1):
        if not row_has_text[y]:
            if not in_gap:
                in_gap = True
                gap_start = y
        else:
            if in_gap:
                gaps.append((gap_start, y))  # [gap_start, y)
                in_gap = False
    # (any trailing gap after last_row is margin, already excluded by range)
    # print(f"{gaps=}")
    if not gaps:
        # no internal gaps at all -> whole content region is one line
        return [(int(first_row), int(last_row) + 1)]

    gap_lengths = np.array([end - start for (start, end) in gaps])
    print(f"Sorted gaps: {np.sort(gap_lengths)}\nGaps:        {gap_lengths}")
    # --- determine split threshold between "diacritic gap" and "line gap" ---
    if min_gap_for_split is None:
        if len(gap_lengths) == 1:
            # only one gap observed; nothing to split against, treat it as a line break
            min_gap_for_split = 0
        else:
            # if there is a small gap and a large gap on every row, then the
            # median gap would still be larger than the size of the small gap,
            # because there would be an equal number of both sizes
            # min_gap_for_split = np.median(gap_lengths)
            # a value right between the min gap and the median gap seems to be
            # valid for a cutoff value; e.g.:
            # for (8, 8, 8, 8, 8, 8, 8, 8) -> (8 + 8)/2 = 8
            # for (1, 8, 8, 8, 8, 8, 8, 8) -> (8 + 1)/2 = 4.5
            # for (1, 1, 1, 1, 8, 8, 8, 8) -> (8 + 1)/2 = 4.5
            # for (1, 2, 3, 6, 7, 8, 9, 10) -> (6.5 + 1)/2 = 3.75
            med_gap = np.median(gap_lengths)
            min_gap = gap_lengths.min()
            gap_ratio = med_gap / min_gap
            print(f"{len(gap_lengths)=}; {med_gap=}; {gap_ratio=}")
            if gap_ratio > 2:
                # assume smallest gaps are not line break gaps
                min_gap_for_split = (med_gap + min_gap) / 2
            else:
                # assume all gaps are line break gaps
                min_gap_for_split = min_gap
        print(f"{min_gap_for_split=}")

    # --- keep only gaps large enough to be real line breaks ---
    line_break_gaps = [(start, end) for (start, end), length in zip(gaps, gap_lengths)
                        if length >= min_gap_for_split]

    # --- build line ranges from content bounds and confirmed line-break gaps ---
    boundaries = [first_row]
    for (start, end) in line_break_gaps:
        boundaries.append(start)      # end of previous line
        boundaries.append(end)        # start of next line
    boundaries.append(last_row + 1)

    lines = []
    for i in range(0, len(boundaries), 2):
        top, bottom = boundaries[i], boundaries[i + 1]
        if bottom > top:  # guard against degenerate zero-height entries
            lines.append((int(top), int(bottom)))

    return lines, min_gap_for_split


def segment_lines(inv, **kwargs):
    return segment_lines_by_whitespace(inv, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--min-gap",
        metavar="INT",
        type=int,
        default=None,
        help="give explicit minimum line gap for row splitting",
    )
    parser.add_argument(
        "--ignore-rotation",
        action="store_true",
        help="skip image rotation before splitting lines",
    )
    parser.add_argument(
        "image",
        metavar="PATH/TO/IMAGE",
        type=Path,
        help="input image to split",
    )
    args = parser.parse_args()

    filestem = args.image.stem
    parent_dir = args.image.parent

    ## (1) read
    img = cv2.imread(args.image)
    # convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ## (2) threshold
    # convert all pixels white if below the threshold, black if above
    th, inv = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

    if args.ignore_rotation:
        rotated_inv = inv
        rotated = cv2.bitwise_not(inv)
    else:
        ## (3) minAreaRect on the nozeros
        pts = cv2.findNonZero(inv)
        (cx, cy), _, ang = cv2.minAreaRect(pts)

        ang = ang % 90  # normalize for perfectly aligned page
        if ang > 45:
            ang -=90

        ## (4) Find rotated matrix, do rotation
        M = cv2.getRotationMatrix2D((cx,cy), ang, 1.0)
        rotated_inv = cv2.warpAffine(inv, M, (img.shape[1], img.shape[0]), borderValue=0)
        rotated = cv2.bitwise_not(rotated_inv)

    lines, min_gap = segment_lines(rotated_inv, min_gap_for_split=args.min_gap)
    # print(f"{lines=}")

    if len(lines) == 0:
        print("Warning: no textline lower bounds found!")
        print(f"{args.image=}")
        print(f"{gray=}")
        print(f"{gray.mean()=}; {gray.min()=}; {gray.max()=}; {gray.mean()=}; {gray.std()=}")
        print(f"{th=}")
        print(f"{ang=}")
        print(f"{rotated.mean()=}; {rotated.min()=}; {rotated.max()=}; {rotated.mean()=}; {rotated.std()=}")
        sys.exit(1)

    # re-colorize the image
    colorized = cv2.cvtColor(rotated, cv2.COLOR_GRAY2BGR)

    for i, (top, bottom) in enumerate(lines):
        # print(f"Checking {y=}")
        outfile = parent_dir / f"{filestem}-L{i + 1}.png"
        # add padding for better tesseract result
        padding = int(min_gap / 2)
        if top > padding:
            top -= padding
        if colorized.shape[0] - bottom > padding:
            bottom += padding
        # assumes same number of indexes in uppers and lowers, and that they
        # alternate
        line_img = colorized[top:bottom, :]
        try:
            cv2.imwrite(outfile, line_img)
            # print(f"Saved {line_img}")
        except cv2.error as e:
            print(f"Error: {e.msg}")


if __name__ == "__main__":
    main()
