"""Build a contact sheet from real device canvas captures and the pinned previews."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[2]
results = root / "validation"
preview = root / "mfilm-canon-film-simulation/ml-dev/filmos/preview"
screens = (("boot", "boot"), ("shelf", "shelf"), ("home", "home"),
           ("roll", "roll"), ("darkroom", "darkroom"), ("developing", "develop"),
           ("prints-sheet", "prints"))
pairs = [(original, sony) for original, sony in screens
         if (results / (sony + "-device.ppm")).is_file()]
sheet = Image.new("RGB", (964, 360 * len(pairs) + 44), "#141414")
draw = ImageDraw.Draw(sheet)
font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 21)
draw.text((12, 8), "M-Film 0.2.4  /  upstream preview", font=font, fill="white")
draw.text((494, 8), "ILCE-5100  /  device canvas", font=font, fill="white")
for index, (original, sony) in enumerate(pairs):
    upstream = Image.open(preview / (original + ".png")).convert("RGB")
    device = Image.open(results / (sony + "-device.ppm")).convert("RGB")
    device.save(results / (sony + "-device.png"))
    y = 44 + index * 360
    sheet.paste(upstream.resize((480, 320), Image.Resampling.LANCZOS), (0, y))
    sheet.paste(device.resize((480, 320), Image.Resampling.LANCZOS), (484, y))
    draw.text((12, y + 323), original, font=font, fill="#edb748")
sheet.save(results / "screen-comparison.jpg", quality=92)

