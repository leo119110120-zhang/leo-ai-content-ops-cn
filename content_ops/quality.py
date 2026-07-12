from pathlib import Path
import re

from PIL import Image, UnidentifiedImageError

from content_ops.models import QAItem, QAReport
from content_ops.storage import load_manifest


REQUIRED_TEXT = (
    "00-brief.md",
    "01-source-pack.md",
    "02-master-draft.md",
    "03-wechat-final.md",
    "04-xhs-final.md",
)
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")


def run_quality_checks(task_dir: Path) -> QAReport:
    items: list[QAItem] = []
    manifest = load_manifest(task_dir)
    sources = manifest.get("sources", [])
    if not sources:
        items.append(
            QAItem(
                "sources.empty",
                "error",
                "至少需要一个可追溯来源",
                "manifest.yaml",
            )
        )
    source_ids = {
        source.get("id") for source in sources if source.get("id")
    }
    for source in sources:
        if (
            source.get("kind") == "web"
            and source.get("current")
            and not source.get("retrieved_at")
        ):
            items.append(
                QAItem(
                    "sources.retrieved_at",
                    "error",
                    f"当前性网页来源缺少检索日期：{source.get('id', '')}",
                    "manifest.yaml",
                )
            )
    claims = manifest.get("claims", [])
    if not claims:
        items.append(
            QAItem(
                "claims.empty",
                "error",
                "至少需要一项带来源的事实声明",
                "manifest.yaml",
            )
        )
    for index, claim in enumerate(claims, start=1):
        linked = set(claim.get("source_ids", []))
        if not linked or not linked.issubset(source_ids):
            items.append(
                QAItem(
                    "claims.unlinked",
                    "error",
                    f"第 {index} 项事实没有关联有效来源",
                    "manifest.yaml",
                )
            )
    packaging = manifest.get("packaging", {})
    expected = {"titles": 5, "covers": 3, "openings": 2}
    for key, count in expected.items():
        if len(packaging.get(key, [])) < count:
            items.append(
                QAItem(
                    f"packaging.{key}",
                    "error",
                    f"{key} 至少需要 {count} 个候选",
                    "manifest.yaml",
                )
            )
    for key in ("reader_payoff", "discussion_question"):
        if not str(packaging.get(key, "")).strip():
            items.append(
                QAItem(
                    f"packaging.{key}",
                    "error",
                    f"缺少 {key}",
                    "manifest.yaml",
                )
            )
    texts: dict[str, str] = {}
    for name in REQUIRED_TEXT:
        path = task_dir / name
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        texts[name] = text
        if len(text.strip()) < 10:
            items.append(
                QAItem(
                    "content.empty",
                    "error",
                    f"内容为空或过短：{name}",
                    name,
                )
            )
        if PHONE_RE.search(text):
            items.append(
                QAItem(
                    "privacy.phone",
                    "error",
                    f"检测到疑似手机号：{name}",
                    name,
                )
            )
    if texts.get("03-wechat-final.md", "").strip() == texts.get(
        "04-xhs-final.md", ""
    ).strip():
        items.append(
            QAItem(
                "platforms.identical",
                "error",
                "公众号与小红书稿件完全相同，尚未完成平台原生适配",
                "03-wechat-final.md",
            )
        )
    image_names = {
        path.name for path in (task_dir / "images").glob("*.png")
    }
    for required in ("wechat-cover.png", "xhs-01.png"):
        if required not in image_names:
            items.append(
                QAItem(
                    "assets.missing",
                    "error",
                    f"缺少图片：{required}",
                    f"images/{required}",
                )
            )
    xhs_images = sorted((task_dir / "images").glob("xhs-*.png"))
    xhs_cards = manifest.get("xhs_cards", [])
    if len(xhs_images) != len(xhs_cards):
        items.append(
            QAItem(
                "assets.card_count",
                "error",
                f"小红书卡片脚本 {len(xhs_cards)} 张，实际图片 {len(xhs_images)} 张",
                "manifest.yaml",
            )
        )
    for index, card in enumerate(xhs_cards, start=1):
        missing_fields = [
            key
            for key in ("eyebrow", "title", "body")
            if not str(card.get(key, "")).strip()
        ]
        if missing_fields:
            items.append(
                QAItem(
                    "assets.card_text",
                    "error",
                    f"第 {index} 张卡片缺少文字字段：{', '.join(missing_fields)}",
                    "manifest.yaml",
                )
            )
    for path in sorted((task_dir / "images").glob("*.png")):
        try:
            with Image.open(path) as image:
                size = image.size
                image.verify()
        except (UnidentifiedImageError, OSError, SyntaxError) as error:
            items.append(
                QAItem(
                    "assets.invalid",
                    "error",
                    f"PNG 无法读取：{path.name}（{error}）",
                    f"images/{path.name}",
                )
            )
            continue
        expected_size = (
            (900, 383) if path.name == "wechat-cover.png" else (1080, 1350)
        )
        if size != expected_size:
            items.append(
                QAItem(
                    "assets.dimensions",
                    "error",
                    f"{path.name} 尺寸为 {size[0]}×{size[1]}，应为 {expected_size[0]}×{expected_size[1]}",
                    f"images/{path.name}",
                )
            )
    return QAReport(
        passed=not any(item.level == "error" for item in items),
        items=items,
    )


def write_quality_report(task_dir: Path, report: QAReport) -> Path:
    lines = [
        "# 质量报告",
        "",
        f"结论：{'通过' if report.passed else '不通过'}",
        "",
    ]
    lines.extend(
        f"- [{item.level}] `{item.code}` {item.message}"
        for item in report.items
    )
    if not report.items:
        lines.append("- 未发现阻塞问题。")
    path = task_dir / "05-quality-report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
