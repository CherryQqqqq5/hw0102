import subprocess
from pathlib import Path

from PIL import Image, ImageDraw


root = Path("work/pdf-qa-v16")
root.mkdir(exist_ok=True)
for index, assignment in enumerate(("一", "二"), 1):
    source = Path("outputs") / f"231880296_邱昱宁_作业{assignment}.pdf"
    subprocess.run(["pdftoppm", "-scale-to-x", "1400", "-scale-to-y", "-1", "-png",
                    str(source), str(root / f"assignment-{index}-page")], check=True)
    rendered_pages = sorted(root.glob(f"assignment-{index}-page-*.png"),
                            key=lambda path: int(path.stem.rsplit("-", 1)[-1]))
    if rendered_pages:
        pages = []
        for target in rendered_pages:
            with Image.open(target) as rendered:
                thumbnail = rendered.convert("RGB")
            thumbnail.thumbnail((650, 920))
            pages.append(thumbnail)
        for start in range(0, len(pages), 4):
            sheet = Image.new("RGB", (1340, 1940), "#e4e7ea")
            draw = ImageDraw.Draw(sheet)
            for offset, page in enumerate(pages[start:start + 4]):
                x = 10 + offset % 2 * 670
                y = 30 + offset // 2 * 970
                draw.text((x, y - 22), f"Assignment {index} / page {start + offset + 1}", fill="black")
                sheet.paste(page, (x, y))
            sheet.save(root / f"assignment-{index}-contact-{start // 4 + 1}.png")
        print({"assignment": index, "rendered_pages": len(pages)})
