from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from content_ops.config import load_yaml


def render_candidates(batch_path: Path, output_path: Path) -> Path:
    batch = load_yaml(batch_path)
    environment = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=select_autoescape(["html"]),
    )
    html = environment.get_template("candidates.html.j2").render(**batch)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
