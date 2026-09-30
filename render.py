"""
İçerik JSON'undan Instagram carousel görselleri (1080x1350 JPEG) üretir.

Kullanım:
    python render.py content/2026-09-30.json            # -> out/2026-09-30/01.jpg ...
    python render.py content/2026-09-30.json --png      # ayrıca PNG de kaydeder
"""
import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
         "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
ORDER = ["teknoloji", "startup", "ekonomi", "spor", "magazin", "siyaset", "bilim", "tarih", "kultur", "zihin", "doga"]


def emphasize(text: str) -> str:
    """'*kelime*' -> vurgulu (italik serif, kategori renginde)."""
    safe = html.escape(text).replace("-", "\u2011")  # tireden satır kırılmasın
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", safe)


def plain(text: str) -> str:
    return text.replace("*", "")


def load(content_path: Path):
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    data = json.loads(content_path.read_text(encoding="utf-8"))
    cats = []
    by_key = {c["key"]: c for c in data["categories"]}
    for key in ORDER:
        if key not in by_key:
            continue
        c = dict(by_key[key])
        meta = cfg["categories"][key]
        c.update(label=meta["label"], color=meta["color"], icon=meta["icon"],
                 headline_html=emphasize(c["headline"]))
        c.setdefault("teaser", plain(c["headline"]))
        cats.append(c)
    for i, c in enumerate(cats, 1):
        c["n"] = i
    return cfg, data, cats


def build_pages(cfg, data, cats, theme: str):
    d = dt.date.fromisoformat(data["date"])
    common = dict(brand_name=cfg["brand_name"], handle=cfg["handle"], theme=theme)
    total = len(cats) + 2
    pages = [dict(kind="cover", index=1, total=total, cover=data["cover"], categories=cats,
                  date_day=d.day, date_month=AYLAR[d.month - 1],
                  date_weekday=GUNLER[d.weekday()], date_year=d.year, **common)]
    for i, c in enumerate(cats, 2):
        pages.append(dict(kind="category", index=i, total=total, c=c, accent=c["color"], **common))
    cta = cfg["cta_line"]
    cta_html = re.sub(r"(06:00)(\S*)", r'<span class="nw"><em>\1</em>\2</span>', html.escape(cta))
    pages.append(dict(kind="cta", index=total, total=total, cta_html=cta_html, **common))
    return pages


def render(content_path: Path, out_dir: Path | None = None, keep_png=False, theme: str = "news") -> list[Path]:
    cfg, data, cats = load(content_path)
    out_dir = (out_dir or ROOT / "out" / data["date"]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True)
    tpl = env.get_template("slide.html.j2")
    files = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        for pg in build_pages(cfg, data, cats, theme):
            html_str = tpl.render(**pg)
            tmp = ROOT / "_render.html"          # fontlar/logo göreli yoldan yüklensin diye
            tmp.write_text(html_str, encoding="utf-8")
            page.goto(tmp.as_uri())
            page.evaluate("document.fonts.ready")
            k = page.evaluate("window.fitText ? window.fitText() : 1")
            if k < 0.7:
                print(f"  ! {pg['index']:02d}: metin uzun, yazı %{int(k*100)}'e küçültüldü — kısaltmak iyi olur")
            png = out_dir / f"{pg['index']:02d}.png"
            page.screenshot(path=str(png))
            jpg = png.with_suffix(".jpg")      # Instagram API yalnızca JPEG kabul eder
            Image.open(png).convert("RGB").save(jpg, "JPEG", quality=94, optimize=True, progressive=True)
            if not keep_png:
                png.unlink()
            files.append(jpg)
            print(f"  ✓ {jpg.relative_to(ROOT)}")
        browser.close()
    tmp.unlink(missing_ok=True)
    (out_dir / "caption.txt").write_text(build_caption(cfg, data, cats), encoding="utf-8")
    return files


def build_caption(cfg, data, cats) -> str:
    if data.get("caption"):
        return data["caption"]
    d = dt.date.fromisoformat(data["date"])
    lines = [f"{d.day} {AYLAR[d.month - 1]} {GUNLER[d.weekday()]} | {data['cover']['title']}",
             "Son 24 saatte öne çıkanlar, tek kaydırmada.", ""]
    for c in cats:
        lines.append(f"• {c['label']}: {c['teaser']}")
    srcs = sorted({s for c in cats for s in c.get("sources", [])})
    lines += ["", "Hangisi seni en çok şaşırttı? Yorumlara yaz.",
              f"Her sabah özet için takip et: {cfg['handle']}", "",
              "Kaynaklar: " + ", ".join(srcs), "", " ".join(cfg["hashtags"])]
    return "\n".join(lines)[:2200]            # Instagram açıklama sınırı


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("content", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--png", action="store_true")
    ap.add_argument("--theme", choices=("news", "facts"), default="news")
    a = ap.parse_args()
    if not a.content.exists():
        sys.exit(f"Bulunamadı: {a.content}")
    render(a.content, a.out, a.png, a.theme)
