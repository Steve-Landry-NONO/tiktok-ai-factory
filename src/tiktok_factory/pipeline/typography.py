"""Responsive, testable Pillow text cards for vertical video."""

from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DEFAULT_FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")


@dataclass(frozen=True)
class TextOverlay:
    text: str
    path: Path
    start_time: float
    end_time: float
    box_x: int
    box_y: int
    box_width: int
    box_height: int
    font_size: int
    line_count: int
    max_lines: int
    safe_zone_ok: bool

    def metadata(self) -> dict[str, object]:
        value = asdict(self)
        value["path"] = str(self.path)
        return value


def _font(size: int, font_path: Path = DEFAULT_FONT) -> ImageFont.FreeTypeFont:
    if not font_path.is_file():
        raise RuntimeError(f"font not found: {font_path}")
    return ImageFont.truetype(str(font_path), size=size)


def measure_wrapped_text(
    text: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int
) -> tuple[list[str], int, int]:
    draw = ImageDraw.Draw(Image.new("L", (1, 1)))
    words = text.split()
    if not words:
        raise ValueError("overlay text must not be empty")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            if not current or len(lines) >= max_lines - 1:
                return [], 0, 0
            lines.append(current)
            current = word
    lines.append(current)
    if len(lines) > max_lines:
        return [], 0, 0
    boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    width = round(max(box[2] - box[0] for box in boxes))
    line_height = round(max(box[3] - box[1] for box in boxes))
    return lines, width, line_height * len(lines) + max(0, len(lines) - 1) * 12


def fit_font_size(
    text: str,
    max_width: int,
    max_height: int,
    max_lines: int,
    initial_size: int = 72,
    minimum_size: int = 42,
    font_path: Path = DEFAULT_FONT,
) -> tuple[ImageFont.FreeTypeFont, list[str], int, int]:
    for size in range(initial_size, minimum_size - 1, -2):
        font = _font(size, font_path)
        lines, width, height = measure_wrapped_text(text, font, max_width, max_lines)
        if lines and width <= max_width and height <= max_height:
            return font, lines, width, height
    raise ValueError(f"text cannot fit in {max_lines} lines at minimum font size {minimum_size}")


def render_text_card(
    text: str,
    destination: Path,
    *,
    start_time: float,
    end_time: float,
    y: int,
    frame_width: int = 1080,
    frame_height: int = 1920,
    max_width_ratio: float = 0.8,
    max_lines: int = 3,
    initial_size: int = 72,
    minimum_size: int = 42,
    font_path: Path = DEFAULT_FONT,
) -> TextOverlay:
    if not 0 <= start_time < end_time:
        raise ValueError("invalid overlay display interval")
    safe_x = round(frame_width * 0.1)
    max_width = min(round(frame_width * max_width_ratio), frame_width - 2 * safe_x)
    padding_x, padding_y = 36, 24
    font, lines, text_width, text_height = fit_font_size(
        text, max_width - 2 * padding_x, 240 - 2 * padding_y, max_lines,
        initial_size, minimum_size, font_path,
    )
    card_width, card_height = text_width + 2 * padding_x, text_height + 2 * padding_y
    x = (frame_width - card_width) // 2
    safe = x >= safe_x and x + card_width <= frame_width - safe_x and y >= 0 and y + card_height <= frame_height
    if not safe:
        raise ValueError("text card violates video safe zones")
    image = Image.new("RGBA", (card_width, card_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, card_width - 1, card_height - 1), radius=24, fill=(0, 0, 0, 178))
    line_y = padding_y
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width, line_height = round(bbox[2] - bbox[0]), round(bbox[3] - bbox[1])
        draw.text(((card_width - line_width) / 2, line_y - bbox[1]), line, font=font, fill="white")
        line_y += line_height + 12
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)
    return TextOverlay(text, destination, start_time, end_time, x, y, card_width, card_height,
                       round(font.size), len(lines), max_lines, safe)
