"""Build the optional Xiaofeixue performance atlas from transparent strips."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


CELL_WIDTH = 192
CELL_HEIGHT = 208
FRAME_COUNT = 8
FOOT_PAD = 5
CONTENT_PAD = 5
ROW_NAMES = ("dance", "fish", "yarn", "coffee", "read", "stars")


def _alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("performance strip is empty")
    return bbox


def extract_row(path: Path) -> list[Image.Image]:
    strip = Image.open(path).convert("RGBA")
    slot_width = strip.width / FRAME_COUNT
    slot_bboxes = []
    for index in range(FRAME_COUNT):
        left = round(index * slot_width)
        right = round((index + 1) * slot_width)
        slot = strip.crop((left, 0, right, strip.height))
        slot_bboxes.append(_alpha_bbox(slot))

    top = min(bbox[1] for bbox in slot_bboxes)
    bottom = max(bbox[3] for bbox in slot_bboxes)
    row_height = bottom - top
    scale = min((CELL_HEIGHT - FOOT_PAD - CONTENT_PAD) / row_height, 1.0)

    frames = []
    for index, bbox in enumerate(slot_bboxes):
        left = round(index * slot_width)
        right = round((index + 1) * slot_width)
        slot = strip.crop((left, top, right, bottom))
        if scale < 1.0:
            slot = slot.resize(
                (max(1, round(slot.width * scale)), max(1, round(slot.height * scale))),
                Image.Resampling.LANCZOS,
            )
        frame = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
        left = (CELL_WIDTH - slot.width) // 2
        frame.alpha_composite(slot, (left, CELL_HEIGHT - FOOT_PAD - slot.height))
        frames.append(frame)
    return frames


def load_row(path: Path) -> list[Image.Image]:
    if not path.is_dir():
        return extract_row(path)
    files = sorted(path.glob("*.png"))
    if len(files) != FRAME_COUNT:
        raise ValueError(f"{path} must contain exactly {FRAME_COUNT} PNG frames")
    frames = []
    for file in files:
        source = Image.open(file).convert("RGBA")
        bbox = _alpha_bbox(source)
        sprite = source.crop(bbox)
        frame = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
        left = (CELL_WIDTH - sprite.width) // 2
        frame.alpha_composite(sprite, (left, CELL_HEIGHT - FOOT_PAD - sprite.height))
        frames.append(frame)
    return frames


def existing_rows(path: Path) -> dict[str, list[Image.Image]]:
    if not path.exists():
        return {}
    atlas = Image.open(path).convert("RGBA")
    if atlas.width != CELL_WIDTH * FRAME_COUNT or atlas.height % CELL_HEIGHT:
        raise ValueError(f"unexpected existing atlas size: {atlas.size}")
    row_count = min(atlas.height // CELL_HEIGHT, len(ROW_NAMES))
    rows = {}
    for row_index, name in enumerate(ROW_NAMES[:row_count]):
        rows[name] = [
            atlas.crop(
                (
                    frame_index * CELL_WIDTH,
                    row_index * CELL_HEIGHT,
                    (frame_index + 1) * CELL_WIDTH,
                    (row_index + 1) * CELL_HEIGHT,
                )
            )
            for frame_index in range(FRAME_COUNT)
        ]
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--existing", type=Path)
    for name in ROW_NAMES:
        parser.add_argument(f"--{name}", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    rows_by_name = existing_rows(args.existing) if args.existing else {}
    for name in ROW_NAMES:
        source = getattr(args, name)
        if source is not None:
            rows_by_name[name] = load_row(source)
    missing = [name for name in ROW_NAMES if name not in rows_by_name]
    if missing:
        raise ValueError(f"missing performance rows: {', '.join(missing)}")
    rows = [rows_by_name[name] for name in ROW_NAMES]
    atlas = Image.new("RGBA", (CELL_WIDTH * FRAME_COUNT, CELL_HEIGHT * len(rows)), (0, 0, 0, 0))
    for row_index, frames in enumerate(rows):
        for frame_index, frame in enumerate(frames):
            atlas.alpha_composite(frame, (frame_index * CELL_WIDTH, row_index * CELL_HEIGHT))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(args.out, "WEBP", lossless=True, quality=100, method=6)
    print(f"Wrote {args.out} ({atlas.width}x{atlas.height})")


if __name__ == "__main__":
    main()
