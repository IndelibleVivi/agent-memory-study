# Reader typefaces

The reader serves these modified WOFF2 subsets from its own origin. No Google Fonts CSS, remote font request, or font-service script is used.

| Shipped face | Upstream | Copyright / license |
| --- | --- | --- |
| AMS Display, roman and italic | [Newsreader](https://github.com/google/fonts/tree/main/ofl/newsreader), variable optical size and weight | Copyright 2020 The Newsreader Project Authors; [SIL OFL 1.1](newsreader-OFL.txt) |
| AMS Text | [Noto Serif SC](https://github.com/google/fonts/tree/main/ofl/notoserifsc), variable weight | Copyright 2012 Google Inc.; [SIL OFL 1.1](notoserifsc-OFL.txt) |
| AMS Sans | [Instrument Sans](https://github.com/google/fonts/tree/main/ofl/instrumentsans), variable width and weight | Copyright 2022 The Instrument Sans Project Authors; [SIL OFL 1.1](instrumentsans-OFL.txt) |

Sources were retrieved from the official `google/fonts` repository on 2026-10-18. The subsets retain upstream copyright, license and version metadata; primary family names are changed to the AMS names above. These font licenses do not license the project's code or editorial content.

The Latin faces include Latin Extended, common punctuation and typographic spaces. The Chinese subset covers the current public data and interface strings; additional characters use the system font fallback until the subset is rebuilt. The four files together are about 0.83 MB. Browsers load faces as needed with `font-display: swap`.

To rebuild, place these unmodified upstream files in a local source directory outside the checkout:

- `newsreader-Newsreader[opsz,wght].ttf`
- `newsreader-Newsreader-Italic[opsz,wght].ttf`
- `notoserifsc-NotoSerifSC[wght].ttf`
- `instrumentsans-InstrumentSans[wdth,wght].ttf`
- `newsreader-OFL.txt`, `notoserifsc-OFL.txt`, `instrumentsans-OFL.txt`

After compiling content, run the optional, isolated build tool:

```sh
uv run --with 'fonttools[woff]==4.67.0' python tools/build_fonts.py /path/to/font-sources
```

The tool reads the generated public corpus, `index.html`, and interface JavaScript for glyph coverage. It makes no network requests. Review the resulting font files and license notices together, then check the actual Chinese/English headings in a browser. Ordinary content builds and CI use the checked-in subsets and do not require fontTools or the source TTFs.
