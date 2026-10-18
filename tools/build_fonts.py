"""Build local OFL font subsets; sources are supplied explicitly, never downloaded.

Run with fonttools[woff]==4.67.0; see assets/fonts/README.md for source filenames.
"""
import argparse
from pathlib import Path
from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]


def build(source: Path):
    destination = ROOT / "assets/fonts"
    destination.mkdir(exist_ok=True)
    public_text = "".join(p.read_text() for p in [
        ROOT / "data/materials.json", ROOT / "index.html",
        *sorted((ROOT / "assets").glob("*.js")),
    ])
    latin = set(range(0x20, 0x0250)) | set(range(0x2000, 0x2070))
    faces = [
        ("newsreader-Newsreader[opsz,wght].ttf", "ams-display", "AMS Display", latin),
        ("newsreader-Newsreader-Italic[opsz,wght].ttf", "ams-display-italic", "AMS Display", latin),
        ("instrumentsans-InstrumentSans[wdth,wght].ttf", "ams-sans", "AMS Sans", latin),
        ("notoserifsc-NotoSerifSC[wght].ttf", "ams-text", "AMS Text", set(map(ord, public_text)) | latin),
    ]
    for filename, output, family, unicodes in faces:
        font = TTFont(source / filename, recalcTimestamp=False)
        options = subset.Options()
        options.name_IDs = [0, 1, 2, 3, 4, 5, 6, 13, 14, 16, 17]
        options.name_legacy = True
        options.name_languages = [0x409]
        sub = subset.Subsetter(options=options)
        sub.populate(unicodes=unicodes)
        sub.subset(font)
        # Modified subsets use new names; copyright/license/version remain intact.
        italic = "italic" in output
        for record in font["name"].names:
            if record.nameID in (1, 16):
                record.string = family
            elif record.nameID in (3, 4):
                record.string = family + (" Italic" if italic else " Regular")
            elif record.nameID == 6:
                record.string = family.replace(" ", "") + ("-Italic" if italic else "-Regular")
        font.flavor = "woff2"
        path = destination / f"{output}.woff2"
        font.save(path)
        print(f"{path.relative_to(ROOT)}: {path.stat().st_size:,} bytes")
    for name in ("newsreader", "notoserifsc", "instrumentsans"):
        (destination / f"{name}-OFL.txt").write_text("\n".join(
            line.rstrip() for line in (source / f"{name}-OFL.txt").read_text().splitlines()
        ) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    build(parser.parse_args().source)
