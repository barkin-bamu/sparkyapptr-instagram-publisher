"""
Günlük çalıştırıcı: içerik JSON'unu doğrular -> görselleri üretir -> Instagram'a paylaşır.

    python run_daily.py                       # bugünün dosyası: content/YYYY-MM-DD.json
    python run_daily.py content/2026-09-30.json
    python run_daily.py --dry-run             # üret ama paylaşma
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from publish import publish_folder, publish_single
from render import ORDER, render
from render_social_formats import make_reel, make_story

ROOT = Path(__file__).resolve().parent


def validate(path: Path):
    d = json.loads(path.read_text(encoding="utf-8"))
    errs = []
    try:
        dt.date.fromisoformat(d.get("date", ""))
    except (TypeError, ValueError):
        errs.append("'date' YYYY-MM-DD biçiminde değil")
    for k in ("date", "cover", "categories"):
        if k not in d:
            errs.append(f"'{k}' alanı yok")
    keys = set()
    for c in d.get("categories", []):
        if c.get("key") not in ORDER:
            errs.append(f"bilinmeyen kategori: {c.get('key')}")
        elif c.get("key") in keys:
            errs.append(f"yinelenen kategori: {c.get('key')}")
        keys.add(c.get("key"))
        if not c.get("headline"):
            errs.append(f"{c.get('key')}: headline boş")
        if len(c.get("headline", "")) > 90:
            errs.append(f"{c.get('key')}: headline çok uzun (>90)")
        if not 1 <= len(c.get("items", [])) <= 3:
            errs.append(f"{c.get('key')}: 1-3 madde olmalı")
        if not c.get("sources"):
            errs.append(f"{c.get('key')}: en az bir kaynak gerekli")
    if not 1 <= len(keys) <= len(ORDER):
        errs.append("1-6 benzersiz kategori gerekli")
    if errs:
        sys.exit("İçerik hatalı:\n - " + "\n - ".join(errs))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("content", nargs="?", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--formats", default="carousel,reel,story", help="virgülle ayrılmış: carousel,reel,story")
    ap.add_argument("--out-dir", type=Path, help="üretilen medya klasörü; haber/fakt akışlarını ayırmak için")
    ap.add_argument("--theme", choices=("news", "facts"), default="news")
    a = ap.parse_args()
    today = dt.datetime.now(ZoneInfo("Europe/Istanbul")).date().isoformat()
    path = a.content or ROOT / "content" / f"{today}.json"
    if not path.exists():
        sys.exit(f"Bugünün içeriği bulunamadı: {path}  (haber agent'ı bu dosyayı üretmeli)")
    validate(path)
    print("1/2 Görseller üretiliyor…")
    files = render(path, out_dir=a.out_dir, theme=a.theme)
    folder = files[0].parent
    formats = {part.strip() for part in a.formats.split(",") if part.strip()}
    unknown = formats - {"carousel", "reel", "story"}
    if unknown:
        sys.exit("Bilinmeyen yayın biçimi: " + ", ".join(sorted(unknown)))
    if formats & {"reel", "story"}:
        print("2/3 Story ve Reel hazırlanıyor…")
        if "story" in formats:
            make_story(folder)
        if "reel" in formats:
            make_reel(folder)
    print("3/3 Instagram'a paylaşılıyor…")
    caption = (folder / "caption.txt").read_text(encoding="utf-8")
    if "carousel" in formats:
        publish_folder(folder, dry_run=a.dry_run)
    if "reel" in formats:
        publish_single(folder, "reel.mp4", "REELS", caption, dry_run=a.dry_run)
    if "story" in formats:
        publish_single(folder, "story.jpg", "STORIES", "", dry_run=a.dry_run)
