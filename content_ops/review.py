from pathlib import Path
import zipfile

from jinja2 import Environment, FileSystemLoader, select_autoescape
import markdown

from content_ops.storage import load_manifest


def build_review_model(task_dir: Path) -> dict:
    manifest = load_manifest(task_dir)
    packaging = manifest.get("packaging", {})

    def read(name: str) -> str:
        return (task_dir / name).read_text(encoding="utf-8")

    return {
        "content_id": manifest["content_id"],
        "title": manifest.get("title", ""),
        "status": manifest["status"],
        "score": manifest.get("score", {}),
        "demand_evidence": manifest.get("demand_evidence", []),
        "differentiation": manifest.get("differentiation", ""),
        "titles": packaging.get("titles", []),
        "covers": packaging.get("covers", []),
        "openings": packaging.get("openings", []),
        "reader_payoff": packaging.get("reader_payoff", ""),
        "discussion_question": packaging.get("discussion_question", ""),
        "sources": manifest.get("sources", []),
        "wechat_raw": read("03-wechat-final.md"),
        "xhs_raw": read("04-xhs-final.md"),
        "wechat_html": markdown.markdown(
            read("03-wechat-final.md"), extensions=["tables"]
        ),
        "xhs_html": markdown.markdown(
            read("04-xhs-final.md"), extensions=["tables"]
        ),
        "quality_html": markdown.markdown(read("05-quality-report.md")),
        "images": [
            path.name for path in sorted((task_dir / "images").glob("*.png"))
        ],
    }


def render_review(task_dir: Path, output_path: Path) -> Path:
    with zipfile.ZipFile(
        task_dir / "images.zip", "w", zipfile.ZIP_DEFLATED
    ) as archive:
        for path in sorted((task_dir / "images").glob("*.png")):
            archive.write(path, arcname=path.name)
    environment = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=select_autoescape(["html"]),
    )
    html = environment.get_template("review.html.j2").render(
        **build_review_model(task_dir)
    )
    output_path.write_text(html, encoding="utf-8")
    return output_path
