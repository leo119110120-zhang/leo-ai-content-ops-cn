from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from content_ops.storage import load_manifest


CARD_SIZE = (1080, 1350)
SUPPORTED_LAYOUTS = {
    "standard",
    "hero_conflict",
    "comment_wall",
    "unknowns",
    "funnel",
    "evidence_stage",
    "timeline",
    "final_split",
}


def _font(size: int, bold: bool = False):
    candidates = (
        Path("C:/Windows/Fonts/msyhbd.ttc") if bold else Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    )
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default(size=size)


def _wrap(
    draw: ImageDraw.ImageDraw, text: str, font, max_width: int
) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if current and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    preferred_size: int,
    minimum_size: int,
    max_lines: int,
):
    for size in range(preferred_size, minimum_size - 1, -2):
        font = _font(size, bold=True)
        lines = _wrap(draw, text, font, max_width)
        has_orphan = len(lines) > 1 and len(lines[-1].strip()) == 1
        if len(lines) <= max_lines and not has_orphan:
            return font, lines
    raise ValueError("text is too long for the configured card area")


def _resolve_asset(task_dir: Path, value: str | None) -> Path | None:
    if not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    for base in (task_dir, Path.cwd()):
        resolved = (base / candidate).resolve()
        if resolved.exists():
            return resolved
    return None


def _background(task_dir: Path, manifest: dict, size: tuple[int, int]) -> Image.Image | None:
    path = _resolve_asset(task_dir, manifest.get("visual_background"))
    if not path:
        return None
    with Image.open(path) as source:
        return ImageOps.fit(source.convert("RGB"), size, Image.Resampling.LANCZOS)


def _pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill: str, color: str = "white") -> None:
    x, y = xy
    font = _font(31, bold=True)
    box = draw.textbbox((0, 0), text, font=font)
    width = box[2] - box[0]
    draw.rounded_rectangle((x, y, x + width + 48, y + 58), radius=29, fill=fill)
    draw.text((x + 24, y + 10), text, font=font, fill=color)


def _draw_lines(draw: ImageDraw.ImageDraw, lines: list[str], font, xy: tuple[int, int], fill: str, gap: int) -> int:
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += gap
    return y


def _title(draw: ImageDraw.ImageDraw, text: str, y: int, color: str, max_width: int = 920, size: int = 76, lines: int = 3) -> int:
    font, wrapped = _fit_text(draw, text, max_width, size, 52, lines)
    return _draw_lines(draw, wrapped, font, (80, y), color, int(font.size * 1.3))


def _footer(draw: ImageDraw.ImageDraw, brand: dict, index: int, color: str) -> None:
    draw.text((80, 1270), brand["name"], font=_font(27, bold=True), fill=color)
    draw.text((934, 1270), f"{index:02d}", font=_font(27, bold=True), fill=color)


def _render_standard(card: dict, brand: dict, index: int) -> Image.Image:
    colors = brand["colors"]
    image = Image.new("RGB", CARD_SIZE, colors["background"])
    draw = ImageDraw.Draw(image)
    _pill(draw, (70, 60), card["eyebrow"], colors["primary"])
    y = _title(draw, card["title"], 220, colors["text"])
    draw.rounded_rectangle((80, y + 20, 1000, y + 30), radius=5, fill=colors["accent"])
    body_font = _font(46)
    body_lines = _wrap(draw, card["body"], body_font, 920)
    if len(body_lines) > 8:
        raise ValueError(f"card {index} body is too long")
    _draw_lines(draw, body_lines, body_font, (80, y + 85), colors["text"], 70)
    _footer(draw, brand, index, colors["primary"])
    return image


def _render_hero(task_dir: Path, manifest: dict, card: dict, brand: dict, index: int) -> Image.Image:
    colors = brand["colors"]
    image = _background(task_dir, manifest, CARD_SIZE) or Image.new("RGB", CARD_SIZE, colors["background"])
    overlay = Image.new("RGBA", CARD_SIZE, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.rounded_rectangle((45, 38, 1035, 510), radius=38, fill=(246, 242, 233, 235))
    odraw.rounded_rectangle((70, 1040, 1010, 1248), radius=32, fill=(32, 36, 44, 238))
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image)
    _pill(draw, (78, 70), card["eyebrow"], colors["primary"])
    _title(draw, card["title"], 165, colors["text"], 860, 84, 3)
    left = card.get("left_metric", "评论很多")
    right = card.get("right_metric", "付款未知")
    draw.text((110, 1085), left, font=_font(49, bold=True), fill="white")
    draw.text((632, 1085), right, font=_font(49, bold=True), fill=colors["accent"])
    draw.line((525, 1090, 575, 1190), fill=colors["accent"], width=18)
    _footer(draw, brand, index, colors["text"])
    return image


def _render_comment_wall(card: dict, brand: dict, index: int) -> Image.Image:
    colors = brand["colors"]
    image = Image.new("RGB", CARD_SIZE, colors["primary"])
    draw = ImageDraw.Draw(image)
    _pill(draw, (70, 60), card["eyebrow"], colors["accent"], colors["text"])
    y = _title(draw, card["title"], 170, "white", 920, 76, 3)
    metrics = card.get("metrics", ["阅读 2008", "留言 86"])
    for pos, metric in zip((80, 550), metrics):
        draw.rounded_rectangle((pos, y + 30, pos + 450, y + 150), radius=26, fill="#F6F2E9")
        draw.text((pos + 35, y + 58), metric, font=_font(42, bold=True), fill=colors["text"])
    bubbles = card.get("bubbles", ["部署", "部署", "部署", "怎么安装", "求文档", "部署"])
    positions = [(80, 760, 420), (475, 720, 890), (650, 890, 990), (95, 960, 500), (420, 1080, 770), (725, 1050, 990)]
    for n, (x1, y1, x2) in enumerate(positions):
        text = bubbles[n % len(bubbles)]
        fill = "white" if n % 3 else colors["accent"]
        text_color = colors["text"]
        draw.rounded_rectangle((x1, y1, x2, y1 + 112), radius=34, fill=fill)
        draw.text((x1 + 30, y1 + 28), text, font=_font(38, bold=True), fill=text_color)
    _footer(draw, brand, index, "white")
    return image


def _render_unknowns(card: dict, brand: dict, index: int) -> Image.Image:
    colors = brand["colors"]
    image = Image.new("RGB", CARD_SIZE, colors["text"])
    draw = ImageDraw.Draw(image)
    _pill(draw, (70, 60), card["eyebrow"], colors["accent"], colors["text"])
    y = _title(draw, card["title"], 175, "white", 920, 74, 3)
    unknowns = card.get("unknowns", ["领取人数", "询价人数", "付款人数", "复购人数"])
    for i, label in enumerate(unknowns[:4]):
        col, row = i % 2, i // 2
        x1, y1 = 80 + col * 470, y + 55 + row * 260
        draw.rounded_rectangle((x1, y1, x1 + 430, y1 + 210), radius=28, fill="#343A46", outline="#606A7A", width=3)
        draw.text((x1 + 30, y1 + 30), label, font=_font(35), fill="#BEC6D4")
        draw.text((x1 + 30, y1 + 85), "未知 ?", font=_font(62, bold=True), fill=colors["accent"])
    _footer(draw, brand, index, "white")
    return image


def _render_funnel(card: dict, brand: dict, index: int) -> Image.Image:
    colors = brand["colors"]
    image = Image.new("RGB", CARD_SIZE, colors["background"])
    draw = ImageDraw.Draw(image)
    _pill(draw, (70, 60), card["eyebrow"], colors["primary"])
    y = _title(draw, card["title"], 175, colors["text"], 920, 72, 3)
    steps = card.get("steps", ["互动", "询价", "预付款", "复购"])
    descriptions = card.get("step_notes", ["内容钩子", "购买意向", "付费验证", "持续价值"])
    for i, step in enumerate(steps[:4]):
        top = y + 35 + i * 170
        active = i == int(card.get("active_step", 0))
        fill = colors["primary"] if active else "#FFFFFF"
        text_color = "white" if active else colors["text"]
        draw.rounded_rectangle((120 + i * 38, top, 960 - i * 38, top + 125), radius=28, fill=fill, outline="#D6D9E0", width=3)
        draw.text((165 + i * 38, top + 30), f"{i + 1:02d}  {step}", font=_font(43, bold=True), fill=text_color)
        if i < len(descriptions):
            draw.text((720 - i * 25, top + 39), descriptions[i], font=_font(28), fill=colors["accent"] if active else "#7A8290")
    _footer(draw, brand, index, colors["primary"])
    return image


def _render_stage(card: dict, brand: dict, index: int) -> Image.Image:
    colors = brand["colors"]
    image = Image.new("RGB", CARD_SIZE, colors["background"])
    draw = ImageDraw.Draw(image)
    level = int(card.get("level", 2))
    _pill(draw, (70, 60), card["eyebrow"], colors["primary"])
    y = _title(draw, card["title"], 175, colors["text"], 920, 70, 3)
    for i, label in enumerate(card.get("levels", ["互动", "询价", "预付款"])):
        top = y + 80 + (2 - i) * 155
        x1 = 110 + i * 175
        fill = colors["accent"] if i + 1 == level else (colors["primary"] if i + 1 < level else "#D9DDE5")
        draw.rounded_rectangle((x1, top, 970, top + 130), radius=26, fill=fill)
        draw.text((x1 + 35, top + 30), f"0{i + 1}  {label}", font=_font(45, bold=True), fill="white" if i + 1 <= level else colors["text"])
    metric = card.get("metric")
    if metric:
        draw.text((110, 1090), metric, font=_font(58, bold=True), fill=colors["text"])
    _footer(draw, brand, index, colors["primary"])
    return image


def _render_timeline(card: dict, brand: dict, index: int) -> Image.Image:
    colors = brand["colors"]
    image = Image.new("RGB", CARD_SIZE, colors["background"])
    draw = ImageDraw.Draw(image)
    _pill(draw, (70, 60), card["eyebrow"], colors["primary"])
    y = _title(draw, card["title"], 175, colors["text"], 920, 72, 3)
    steps = card.get("timeline", ["D1—2  做3—5页样张", "D3  明确交付并发布", "D4—6  记录询价和付款", "D7  复盘，决定继续或换题"])
    draw.line((130, y + 70, 130, y + 640), fill=colors["primary"], width=12)
    for i, step in enumerate(steps[:4]):
        top = y + 45 + i * 170
        draw.ellipse((100, top, 160, top + 60), fill=colors["accent"] if i == 3 else colors["primary"])
        draw.rounded_rectangle((205, top - 10, 985, top + 112), radius=26, fill="white")
        draw.text((240, top + 22), step, font=_font(38, bold=True), fill=colors["text"])
    _footer(draw, brand, index, colors["primary"])
    return image


def _render_final_split(card: dict, brand: dict, index: int) -> Image.Image:
    colors = brand["colors"]
    image = Image.new("RGB", CARD_SIZE, colors["background"])
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 540, 1350), fill=colors["primary"])
    draw.rectangle((540, 0, 1080, 1350), fill=colors["text"])
    _pill(draw, (70, 60), card["eyebrow"], colors["accent"], colors["text"])
    draw.text((80, 245), "免费", font=_font(86, bold=True), fill="white")
    draw.text((80, 370), "负责涨粉", font=_font(58, bold=True), fill="white")
    draw.text((620, 245), "付费", font=_font(86, bold=True), fill=colors["accent"])
    draw.text((620, 370), "负责验生意", font=_font(58, bold=True), fill="white")
    draw.rounded_rectangle((80, 650, 1000, 1080), radius=38, fill="#F6F2E9")
    _title(draw, card["title"], 720, colors["text"], 820, 70, 3)
    body_font = _font(38)
    body_lines = _wrap(draw, card["body"], body_font, 820)
    _draw_lines(draw, body_lines, body_font, (130, 930), colors["text"], 58)
    _footer(draw, brand, index, "white")
    return image


def render_xhs_cards(task_dir: Path, brand: dict) -> list[Path]:
    manifest = load_manifest(task_dir)
    cards = manifest.get("xhs_cards", [])
    if not cards:
        raise ValueError("manifest.xhs_cards must contain at least one card")
    output = task_dir / "images"
    output.mkdir(exist_ok=True)
    renderers = {
        "standard": lambda card, index: _render_standard(card, brand, index),
        "hero_conflict": lambda card, index: _render_hero(task_dir, manifest, card, brand, index),
        "comment_wall": lambda card, index: _render_comment_wall(card, brand, index),
        "unknowns": lambda card, index: _render_unknowns(card, brand, index),
        "funnel": lambda card, index: _render_funnel(card, brand, index),
        "evidence_stage": lambda card, index: _render_stage(card, brand, index),
        "timeline": lambda card, index: _render_timeline(card, brand, index),
        "final_split": lambda card, index: _render_final_split(card, brand, index),
    }
    paths = []
    for index, card in enumerate(cards, start=1):
        layout = card.get("layout", "standard")
        if layout not in SUPPORTED_LAYOUTS:
            raise ValueError(f"unknown card layout: {layout}")
        try:
            image = renderers[layout](card, index)
        except ValueError as error:
            if "text is too long" in str(error):
                raise ValueError(f"card {index} title is too long") from error
            raise
        path = output / f"xhs-{index:02d}.png"
        image.save(path, format="PNG", optimize=True)
        paths.append(path)
    return paths


def render_wechat_cover(task_dir: Path, brand: dict) -> Path:
    manifest = load_manifest(task_dir)
    covers = manifest.get("packaging", {}).get("covers", [])
    if not covers:
        raise ValueError("manifest.packaging.covers must contain at least one candidate")
    colors = brand["colors"]
    image = _background(task_dir, manifest, (900, 383)) or Image.new("RGB", (900, 383), colors["background"])
    overlay = Image.new("RGBA", (900, 383), (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    draw_overlay.rounded_rectangle((24, 24, 600, 359), radius=28, fill=(246, 242, 233, 235))
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image)
    _pill(draw, (45, 42), "AI生意实验", colors["primary"])
    try:
        cover_font, title_lines = _fit_text(draw, covers[0], 500, 56, 42, 3)
    except ValueError as error:
        raise ValueError("wechat cover title is too long") from error
    _draw_lines(draw, title_lines, cover_font, (45, 125), colors["text"], 70)
    draw.text((45, 325), brand["name"], font=_font(22, bold=True), fill=colors["primary"])
    path = task_dir / "images" / "wechat-cover.png"
    image.save(path, format="PNG", optimize=True)
    return path
