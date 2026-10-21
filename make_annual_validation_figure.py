"""Create the annual-observation figure as an embedded-font vector PDF and 600-dpi PNG."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
FIGURES = ROOT / "figures"
WIDTH, HEIGHT = 1600, 750
WIDTH_CM, HEIGHT_CM = 16.0, 7.5
DPI = 600
SCALE = DPI * WIDTH_CM / 2.54 / WIDTH

INK = "#111111"
GRID = "#D9D9D9"
GREY = "#777777"
ORANGE = "#BE762C"
BLUE = "#126E91"
GREEN = "#4E805A"
RED = "#BC4639"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def font_paths() -> tuple[Path, Path]:
    regular = Path(os.environ.get("QILIAN_TIMES_FONT", r"C:\Windows\Fonts\times.ttf"))
    bold = Path(r"C:\Windows\Fonts\timesbd.ttf")
    if not regular.is_file() or not bold.is_file():
        raise FileNotFoundError("Times New Roman regular and bold fonts are required for the figure.")
    return regular, bold


class FigurePainter:
    def __init__(self, pdf_path: Path, png_path: Path):
        regular, bold = font_paths()
        pdfmetrics.registerFont(TTFont("FigureTimes", str(regular)))
        pdfmetrics.registerFont(TTFont("FigureTimes-Bold", str(bold)))
        self.pdf_path = pdf_path
        self.png_path = png_path
        self.pdf = canvas.Canvas(str(pdf_path), pagesize=(WIDTH_CM / 2.54 * 72, HEIGHT_CM / 2.54 * 72), pageCompression=1)
        self.pdf.setTitle("Annual observations and MODIS NPP comparison")
        self.pdf.setAuthor("")
        self.pdf.scale(WIDTH_CM / 2.54 * 72 / WIDTH, WIDTH_CM / 2.54 * 72 / WIDTH)
        self.image = Image.new("RGB", (round(WIDTH * SCALE), round(HEIGHT * SCALE)), "white")
        self.draw = ImageDraw.Draw(self.image)
        self.font_regular = regular
        self.font_bold = bold

    def line(self, x1: float, y1: float, x2: float, y2: float, color: str = INK,
             width: float = 1.0, dash: tuple[int, ...] | None = None) -> None:
        self.pdf.saveState()
        self.pdf.setStrokeColor(color)
        self.pdf.setLineWidth(width)
        if dash:
            self.pdf.setDash(dash)
        self.pdf.line(x1, HEIGHT - y1, x2, HEIGHT - y2)
        self.pdf.restoreState()
        p1, p2 = (round(x1 * SCALE), round(y1 * SCALE)), (round(x2 * SCALE), round(y2 * SCALE))
        if dash:
            dx, dy = x2 - x1, y2 - y1
            distance = math.hypot(dx, dy)
            pattern = list(dash)
            offset, index = 0.0, 0
            while offset < distance:
                segment = min(float(pattern[index % len(pattern)]), distance - offset)
                if index % 2 == 0:
                    a, b = offset / distance, (offset + segment) / distance
                    self.draw.line(
                        [(round((x1 + dx * a) * SCALE), round((y1 + dy * a) * SCALE)),
                         (round((x1 + dx * b) * SCALE), round((y1 + dy * b) * SCALE))],
                        fill=color, width=max(1, round(width * SCALE)))
                offset += segment
                index += 1
        else:
            self.draw.line([p1, p2], fill=color, width=max(1, round(width * SCALE)))

    def circle(self, x: float, y: float, radius: float, color: str) -> None:
        self.pdf.setFillColor(color)
        self.pdf.circle(x, HEIGHT - y, radius, stroke=0, fill=1)
        r = radius * SCALE
        self.draw.ellipse((x * SCALE - r, y * SCALE - r, x * SCALE + r, y * SCALE + r), fill=color)

    def text(self, x: float, y: float, value: str, size_pt: float = 8.25,
             anchor: str = "middle", bold: bool = False, rotate: int = 0) -> None:
        face = "FigureTimes-Bold" if bold else "FigureTimes"
        self.pdf.saveState()
        self.pdf.setFillColor(INK)
        self.pdf.setFont(face, size_pt)
        xp, yp = x, HEIGHT - y
        if rotate:
            self.pdf.translate(xp, yp)
            self.pdf.rotate(rotate)
            self.pdf.drawCentredString(0, 0, value)
        elif anchor == "start":
            self.pdf.drawString(xp, yp, value)
        elif anchor == "end":
            self.pdf.drawRightString(xp, yp, value)
        else:
            self.pdf.drawCentredString(xp, yp, value)
        self.pdf.restoreState()

        px = round(x * SCALE)
        py = round(y * SCALE)
        fontfile = self.font_bold if bold else self.font_regular
        font = ImageFont.truetype(str(fontfile), round(size_pt * DPI / 72))
        if rotate:
            layer = Image.new("RGBA", (1200, 160), (255, 255, 255, 0))
            layer_draw = ImageDraw.Draw(layer)
            layer_draw.text((600, 80), value, font=font, fill=INK, anchor="mm")
            layer = layer.rotate(rotate, expand=True)
            self.image.paste(layer, (round(px - layer.width / 2), round(py - layer.height / 2)), layer)
            self.draw = ImageDraw.Draw(self.image)
        else:
            pil_anchor = {"start": "ls", "end": "rs", "middle": "ms"}[anchor]
            self.draw.text((px, py), value, font=font, fill=INK, anchor=pil_anchor)

    def finish(self) -> None:
        self.pdf.showPage()
        self.pdf.save()
        self.image.save(self.png_path, dpi=(DPI, DPI), optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--png", type=Path, default=ROOT.parent / "投稿材料" / "图件" / "Figure_11.png")
    args = parser.parse_args()
    FIGURES.mkdir(parents=True, exist_ok=True)
    args.png.parent.mkdir(parents=True, exist_ok=True)
    pdf_path = FIGURES / "fig_annual_validation.pdf"
    painter = FigurePainter(pdf_path, args.png)

    series = read_rows(DATA / "r67_annual_series.csv")
    npp = read_rows(DATA / "r67_NPP_annual.csv")
    associations = read_rows(DATA / "r67_NPP_associations.csv")
    npp_by_year = {int(row["year"]): row for row in npp}
    if len(series) != 19 or set(int(row["year"]) for row in series) != set(npp_by_year):
        raise ValueError("Annual index and NPP files must cover the same 19 years.")
    data = [(row, npp_by_year[int(row["year"])]) for row in series]

    def corr(index: str, comparison: str) -> float:
        row = next(row for row in associations if row["index"] == index and row["comparison"] == comparison)
        return float(row["pearson_r"])

    def x_map(value: float, left: float, right: float, low: float, high: float) -> float:
        return left + (value - low) / (high - low) * (right - left)

    def y_map(value: float, top: float, bottom: float) -> float:
        return bottom - value * (bottom - top)

    # Panel a: same-release control separates observation frequency from product revision.
    left, right, top, bottom = 145, 820, 105, 500
    painter.text(78, 68, "a", size_pt=8.9, anchor="start", bold=True)
    for value in (0, .2, .4, .6, .8, 1.0):
        y = y_map(value, top, bottom)
        painter.line(left, y, right, y, GRID, .55)
        painter.text(125, y + 3, f"{value:.1f}", 8.1, "end")
    painter.line(left, top, left, bottom, INK, .7)
    painter.line(left, bottom, right, bottom, INK, .7)
    for year in (2005, 2010, 2015, 2020, 2023):
        x = x_map(year, left, right, 2005, 2023)
        painter.line(x, bottom, x, bottom + 7, INK, .6)
        painter.text(x, bottom + 22, str(year), 8.1)
    painter.text((left + right) / 2, 562, "Year", 8.5)
    painter.text(38, 335, "Regional index", 8.5, rotate=90)

    specs = [
        ("reconstructed_esi", GREY, None, 1.15),
        ("same_release_5epoch_esi", ORANGE, (5, 3), 1.05),
        ("annual_esi", BLUE, None, 1.4),
        ("first_year_zero_esi", GREEN, (2, 2), 1.05),
    ]
    for column, color, dash, width in specs:
        points = [(x_map(float(row["year"]), left, right, 2005, 2023),
                   y_map(float(row[column]), top, bottom)) for row, _ in data]
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            painter.line(x1, y1, x2, y2, color, width, dash)
        if column == "annual_esi":
            for x, y in points:
                painter.circle(x, y, 2.25, color)

    legends = [
        ("Legacy five-epoch", GREY, 152, 620, None),
        ("CLCD v1.0.5 five-epoch", ORANGE, 488, 620, (5, 3)),
        ("CLCD v1.0.5 annual", BLUE, 152, 675, None),
        ("Annual, first rate zero", GREEN, 488, 675, (2, 2)),
    ]
    for label, color, x, y, dash in legends:
        painter.line(x, y - 3, x + 33, y - 3, color, 1.25, dash)
        painter.text(x + 43, y, label, 8.05, "start")

    # Panel b: external productivity is context, not event-labelled validation.
    bleft, bright, btop, bbottom = 1040, 1540, 105, 500
    painter.text(980, 68, "b", 8.9, "start", bold=True)
    level_r = corr("annual_esi", "levels")
    change_r = corr("annual_esi", "first_differences")
    painter.text((bleft + bright) / 2, 68,
                 f"Level r = {level_r:.3f}; first-difference r = {change_r:.3f}", 8.1)
    for value in (0, .2, .4, .6, .8, 1.0):
        y = y_map(value, btop, bbottom)
        painter.line(bleft, y, bright, y, GRID, .55)
        painter.text(bleft - 18, y + 3, f"{value:.1f}", 8.1, "end")
    painter.line(bleft, btop, bleft, bbottom, INK, .7)
    painter.line(bleft, bbottom, bright, bbottom, INK, .7)
    for value in (.18, .20, .22, .24, .26):
        x = x_map(value, bleft, bright, .18, .27)
        painter.line(x, bbottom, x, bbottom + 7, INK, .6)
        painter.text(x, bbottom + 22, f"{value:.2f}", 8.1)
    painter.text((bleft + bright) / 2, 562, "MODIS NPP (kg C m⁻² yr⁻¹)", 8.5)
    painter.text(925, 335, "Annual-input index", 8.5, rotate=90)
    point_2014 = None
    for row, npp_row in data:
        value = float(npp_row["common_mask_npp_kgC_m2_yr"])
        x = x_map(value, bleft, bright, .18, .27)
        y = y_map(float(row["annual_esi"]), btop, bbottom)
        color = RED if int(row["year"]) == 2014 else BLUE
        radius = 3.1 if int(row["year"]) == 2014 else 2.2
        painter.circle(x, y, radius, color)
        if int(row["year"]) == 2014:
            point_2014 = (x, y)
    if point_2014:
        lx, ly = 1200, 150
        painter.text(lx, ly, "2014 QC 62.1%", 8.05, "start")
        painter.line(lx + 84, ly - 3, point_2014[0] - 8, point_2014[1] - 7, GREY, .65)

    painter.finish()
    shutil.copyfile(args.png, FIGURES / "fig_annual_validation.png")
    audit = {
        "pdf": str(pdf_path), "png": str(args.png), "width_cm": WIDTH_CM,
        "height_cm": HEIGHT_CM, "dpi": DPI, "pixels": list(painter.image.size),
        "font": "Times New Roman", "minimum_text_pt": 8.05, "maximum_text_pt": 8.9,
        "years": len(series), "level_r": level_r, "first_difference_r": change_r,
    }
    (FIGURES / "fig_annual_validation_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
