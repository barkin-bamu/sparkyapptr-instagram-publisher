"""Derive a 9:16 Story image and a silent Reel from a rendered carousel."""
import argparse
import subprocess
from pathlib import Path

from PIL import Image, ImageFilter


def make_story(folder: Path) -> Path:
    cover = Image.open(folder / "01.jpg").convert("RGB")
    canvas = Image.new("RGB", (1080, 1920), "#0D1324")
    background = cover.resize((1080, 1920)).filter(ImageFilter.GaussianBlur(30))
    canvas.paste(background)
    cover.thumbnail((960, 1200))
    x, y = (1080 - cover.width) // 2, (1920 - cover.height) // 2
    canvas.paste(cover, (x, y))
    target = folder / "story.jpg"
    canvas.save(target, "JPEG", quality=94, optimize=True)
    return target


def make_reel(folder: Path) -> Path:
    slides = sorted(folder.glob("[0-9][0-9].jpg"))
    if len(slides) < 2:
        raise ValueError("Reel için en az iki carousel slaytı gerekli")
    command = ["ffmpeg", "-y"]
    for slide in slides:
        command += ["-loop", "1", "-t", "2", "-i", str(slide)]
    filters = []
    for i in range(len(slides)):
        filters.append(f"[{i}:v]scale=1080:1350,pad=1080:1920:0:285:color=0x0D1324,setsar=1[v{i}]")
    filters.append("".join(f"[v{i}]" for i in range(len(slides))) + f"concat=n={len(slides)}:v=1:a=0,format=yuv420p[v]")
    target = folder / "reel.mp4"
    command += ["-filter_complex", ";".join(filters), "-map", "[v]", "-r", "30", "-movflags", "+faststart", str(target)]
    subprocess.run(command, check=True)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    print(f"✓ {make_story(args.folder)}")
    print(f"✓ {make_reel(args.folder)}")
