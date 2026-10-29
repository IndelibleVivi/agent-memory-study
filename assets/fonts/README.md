# Reader typefaces

The reader serves these modified WOFF2 subsets from its own origin. No Google Fonts CSS, remote font request, or font-service script is used.

| Shipped face | Upstream | Copyright / license |
| --- | --- | --- |
| AMS Display, roman and italic | [Newsreader](https://github.com/google/fonts/tree/main/ofl/newsreader), variable optical size and weight | Copyright 2020 The Newsreader Project Authors; [SIL OFL 1.1](newsreader-OFL.txt) |
| AMS Text | [Noto Serif SC](https://github.com/google/fonts/tree/main/ofl/notoserifsc), variable weight | Copyright 2012 Google Inc.; [SIL OFL 1.1](notoserifsc-OFL.txt) |
| AMS Sans | [Instrument Sans](https://github.com/google/fonts/tree/main/ofl/instrumentsans), variable width and weight | Copyright 2022 The Instrument Sans Project Authors; [SIL OFL 1.1](instrumentsans-OFL.txt) |
| AMS UI | [Noto Sans SC](https://github.com/google/fonts/tree/main/ofl/notosanssc), variable weight | Copyright 2014–2021 Adobe; [SIL OFL 1.1](notosanssc-OFL.txt) |

Sources were retrieved from the official `google/fonts` repository on 2026-10-18. The subsets retain upstream copyright, license and version metadata; primary family names are changed to the AMS names above. These font licenses do not license the project's code or editorial content.

The Latin faces include Latin Extended, common punctuation and typographic spaces. The Chinese subset covers the current public data and interface strings; additional characters use the system font fallback until the subset is rebuilt. The four original faces together are about 0.85 MB. Browsers load faces as needed with `font-display: swap`.

AMS Text was refreshed on 2026-10-30 to cover the expanded public corpus, from
the official font blob `eab063faf229160a52d3760f5555150e4eb9e5bf`; the OFL notice
is unchanged. All five subsets together are approximately 1.19 MB.

The additional AMS UI subset was retrieved from the same official repository on
2026-10-29. It provides Chinese interface glyphs for the next reader without a
system Chinese font, and adds approximately 0.34 MB. Its modified family name is
AMS UI; the upstream reserved name is not used for the derivative. Private input
may contain characters outside the public-text subset and then uses the device's
fallback fonts. No font request is sent to a remote service.

To rebuild, place these unmodified upstream files in a local source directory outside the checkout:

- `newsreader-Newsreader[opsz,wght].ttf`
- `newsreader-Newsreader-Italic[opsz,wght].ttf`
- `notoserifsc-NotoSerifSC[wght].ttf`
- `instrumentsans-InstrumentSans[wdth,wght].ttf`
- `notosanssc-NotoSansSC[wght].ttf`
- `newsreader-OFL.txt`, `notoserifsc-OFL.txt`, `instrumentsans-OFL.txt`, `notosanssc-OFL.txt`

After compiling content, run the optional, isolated build tool:

```sh
uv run --with 'fonttools[woff]==4.67.0' python tools/build_fonts.py /path/to/font-sources
```

The tool reads the generated public corpus, interface JavaScript,
the React reader source, and local-service messages for glyph coverage. It makes
no network requests. `--face ams-ui` rebuilds only that face and its license from
an explicitly supplied source directory. Review the resulting font files and
license notices together, then check the actual Chinese/English headings in a
browser. Ordinary content builds and CI use the checked-in subsets and do not
require fontTools or the source TTFs.
