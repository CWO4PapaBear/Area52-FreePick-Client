from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parent
OUT = Path(sys.argv[1])
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def render():
    from PIL import Image, ImageDraw, ImageFont
    report = json.loads((OUT / "progress.json").read_text())
    scale, width, height = 2, 1100, 550
    image = Image.new("RGB", (width * scale, height * scale), (7, 20, 34))
    draw = ImageDraw.Draw(image)
    gold, white, muted, yellow, green = (213, 165, 70), (229, 231, 231), (155, 174, 187), (255, 230, 50), (94, 222, 128)
    def font(size, serif=False):
        choices = [Path("C:/Windows/Fonts/georgiab.ttf" if serif else "C:/Windows/Fonts/segoeuib.ttf"), Path("/mnt/c/Windows/Fonts/georgiab.ttf" if serif else "/mnt/c/Windows/Fonts/segoeuib.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if serif else "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]
        selected = next((path for path in choices if path.is_file()), None)
        if not selected:
            raise RuntimeError("No approved progress graphic font is available")
        return ImageFont.truetype(str(selected), size * scale)
    def rect(box, fill=None, outline=None, line_width=1):
        draw.rounded_rectangle(tuple(int(v * scale) for v in box), radius=8 * scale, fill=fill, outline=outline, width=line_width * scale)
    def text(x, y, value, size=25, color=white, anchor="la", serif=False):
        draw.text((x * scale, y * scale), value, font=font(size, serif), fill=color, anchor=anchor)
    rect((6, 6, width - 7, height - 7), outline=gold, line_width=2)
    rect((13, 13, width - 14, height - 14), outline=(69, 68, 54))
    icon_path = ROOT / "CertificationIcon.tga"
    if not icon_path.is_file():
        raise RuntimeError("Packaged Bear Cave progress icon is missing")
    if icon_path.is_file():
        icon = Image.open(icon_path).convert("RGBA").resize((78 * scale, 78 * scale), Image.Resampling.LANCZOS)
        image.paste(icon, (29 * scale, 28 * scale), icon)
    text(124, 30, "MAKING PROGRESS", 35, gold, serif=True)
    text(126, 80, "AREA 52  •  FREE PICK ALPHA", 18, muted)
    text(1050, 43, report["reporting_date"], 16, muted, "ra")
    draw.line((32 * scale, 127 * scale, 1068 * scale, 127 * scale), fill=gold, width=scale)
    text(45, 149, "CATEGORY", 17, muted)
    text(480, 149, "TOTAL IN GAME", 17, muted, "ma")
    text(706, 149, "VERIFIED", 19, yellow, "ma")
    text(950, 149, "CERTIFIED", 19, green, "ma")
    for index, name in enumerate(("Abilities", "Talents", "Mystic Enchants")):
        y, values = 192 + index * 84, report["categories"][name]
        rect((31, y, 1068, y + 73), fill=(12, 32, 49) if index % 2 == 0 else (9, 26, 42), outline=(34, 50, 58))
        text(47, y + 20, name, 25, gold, serif=True)
        text(480, y + 20, f'{values["Total"]:,}', 26, white, "ma")
        text(706, y + 20, f'{values["VERIFIED"]:,} ({values["verified_percent"]:.1f}%)', 25, yellow, "ma")
        text(950, y + 20, f'{values["CERTIFIED"]:,} ({values["certified_percent"]:.1f}%)', 25, green, "ma")
    text(45, 474, "VERIFIED: engineering checks passed    •    CERTIFIED: confirmed by testers", 18, muted)
    text(45, 505, "Each entry is counted once in its current status.", 16, muted)
    public = OUT
    public.mkdir(parents=True, exist_ok=True)
    target = public / "progress.png"
    image.resize((width, height), Image.Resampling.LANCZOS).save(target, optimize=True)
    print(json.dumps({"path": str(target), "bytes": target.stat().st_size, "sha256": sha(target)}))



if __name__ == '__main__':
    render()
