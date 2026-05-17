# spectacles · brand assets

This folder contains the logo, wordmark, social card, and banner for the
`spectacles` repository. Each asset ships in two themes — **light** (ink on
parchment) and **dark** (parchment on ink) — and in two formats — **SVG** (source,
infinitely scalable) and **PNG** (rasterized for places that can't render SVG).

---

## Concept

Spectacles is a spec-driven development agent suite. The mark visualises the
product's reason for being: **one spec enters, is observed through a pair of
optical instruments, and fans out into many agentic actions.** Read
left-to-right:

```text
spec input → observation lens → decision lens → fan-out → plan / execute / review
```

The visual register is **retro academic** — like a labeled figure in an
old technical manual. Page rules, Roman-numeral callouts, italic figure captions,
and corner brackets all reinforce that.

---

## Colors

| Role                 | Light theme | Dark theme  |
| -------------------- | ----------- | ----------- |
| Primary (ink / page) | `#1a1f2e`   | `#f4ecd8`   |
| Surface              | `#f4ecd8`   | `#1a1f2e`   |
| Brass accent         | `#b8862a`   | `#d4a445`   |
| Muted secondary text | `#5a5246`   | `#a8a08c`   |
| Tertiary text / rules| `#8a8276`   | `#8a8276`   |

The brass tone is slightly brighter in dark theme to compensate for the
inverted background. Use brass sparingly — it marks the **active/output**
state. In every asset, the right lens of the spectacles and the three
fan-out action nodes are brass; everything else is ink/cream.

---

## Typography

**Fraunces** is the only typeface used. It's a free, open-source serif from
Undercase Type, available on Google Fonts.

- Source: <https://fonts.google.com/specimen/Fraunces>
- Weights used: **400 (regular)** and **500 (medium)**
- Styles used: Roman and *italic*

Hierarchy:

| Use              | Weight  | Style   | Notes                                          |
| ---------------- | ------- | ------- | ---------------------------------------------- |
| Wordmark         | 500     | Roman   | Tight letterspacing (`-1px` to `-1.5px`)       |
| Headings / labels| 500     | Roman   | Sentence case                                  |
| Tagline          | 400     | Italic  | Tracked-out caps (`letter-spacing: 3px+`)      |
| Figure captions  | 400     | Italic  | "Fig. 01 — …"                                  |
| Callout numerals | 500     | Italic  | Lowercase Roman numerals in brass (i. ii. iii.)|

If Fraunces isn't available in a given context, the SVGs fall back to
Georgia → Times New Roman → generic serif. This degrades gracefully but
loses the distinctive ball terminals — install Fraunces wherever possible.

---

## Files

### Logos

| File                       | Size           | Use                                          |
| -------------------------- | -------------- | -------------------------------------------- |
| `logo-light.svg/png`       | 1024 × 320     | Horizontal mark on light surfaces            |
| `logo-dark.svg/png`        | 1024 × 320     | Horizontal mark on dark surfaces             |
| `favicon-light.svg/png`    | 512 × 512      | Simplified square mark (spectacles + brass)  |
| `favicon-dark.svg/png`     | 512 × 512      | Same, for dark UI                            |

Use the favicon variants anywhere the mark needs to fit a square — browser
tab, GitHub avatar (square crop), app icons, social profiles. The DAG
branches are stripped so the silhouette stays legible at small sizes.

### Wordmark lockup

| File                       | Size           | Use                                          |
| -------------------------- | -------------- | -------------------------------------------- |
| `wordmark-light.svg/png`   | 800 × 360      | Mark + wordmark + tagline, stacked           |
| `wordmark-dark.svg/png`    | 800 × 360      | Same, for dark surfaces                      |

Use this when you need the full brand introduction — landing pages,
presentation title slides, documentation home page.

### Social card (Open Graph)

| File                          | Size           | Use                                       |
| ----------------------------- | -------------- | ----------------------------------------- |
| `social-card-light.svg/png`   | 1280 × 640     | OG image for repo                         |
| `social-card-dark.svg/png`    | 1280 × 640     | Same, dark theme                          |

See [Setting the repository social-preview card](#setting-the-repository-social-preview-card)
below for the setup step.

### Banner

| File                       | Size           | Use                                          |
| -------------------------- | -------------- | -------------------------------------------- |
| `banner-light.svg/png`     | 1500 × 500     | README hero image, GitHub repo banner        |
| `banner-dark.svg/png`      | 1500 × 500     | Same, dark theme                             |

Drop into the top of `README.md`. For GitHub light/dark theme support:

```markdown
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/png/banner-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="./assets/png/banner-light.png">
  <img alt="spectacles — a spec-driven agent suite for GitHub Actions" src="./assets/png/banner-light.png">
</picture>
```

---

## Usage rules

- **Don't recolor the mark.** Ink on parchment, parchment on ink, brass for
  accents — that's the system. If a third color is genuinely needed for a
  new asset, it should come from the muted secondary palette, not a new hue.
- **Don't compress the wordmark.** Fraunces is doing a lot of the work; if
  you have to scrunch it to fit, you need a wider layout.
- **The brass dot is load-bearing.** It encodes "active output." Keep it on
  the right lens of the spectacles and on the fan-out nodes.
- **Roman-numeral callouts only.** When extending the visual system to new
  diagrams (`Fig. 02`, etc.), keep lowercase italic Roman numerals — `i.`,
  `ii.`, `iii.` — in brass. This is the through-line that ties everything
  back to the manual-page metaphor.
- **Sentence case everywhere.** Even the wordmark is lowercase. Never
  "Spectacles" or "SPECTACLES" except in tracked-out italic tagline blocks.

---

## Setting the repository social-preview card

The social-preview card is what GitHub renders when a repository, issue, or
pull request link is shared (Open Graph / Twitter Card). It is a repository
setting, not a tracked file, so it is applied once by an operator from the
card image committed under `docs/assets/png/`.

Steps:

1. Open the repository on GitHub and go to **Settings**.
2. In the **General** tab, scroll to the **Social preview** section.
3. Choose **Edit** (or **Upload an image…**) and select the card from this
   repository at `docs/assets/png/social-card-light.png`. GitHub recommends a
   1280 × 640 image; the committed card matches that size.
4. Save. The new card takes effect for subsequent link previews. Use
   `social-card-dark.png` instead if a dark variant is preferred.

This step has no code artifact: it changes a repository setting only. The
card image source lives under `docs/assets/png/` so it stays versioned and
reproducible.

### Verification

- The card image exists at `docs/assets/png/social-card-light.png` (and the
  dark variant at `docs/assets/png/social-card-dark.png`), each 1280 × 640.
- After the operator applies the setting, the repository's **Settings →
  General → Social preview** section shows the brand card, and a freshly
  shared repository, issue, or pull request link renders that card.

---

## Regenerating PNGs from SVG

The PNGs in this folder are rendered from the SVGs with [CairoSVG](https://cairosvg.org/)
and Fraunces installed system-wide. If you change an SVG and need to
regenerate:

```bash
pip install cairosvg
# install Fraunces locally first — see https://fonts.google.com/specimen/Fraunces
python3 -c "
import cairosvg
jobs = [
    ('logo-light.svg',         1024),
    ('logo-dark.svg',          1024),
    ('favicon-light.svg',       512),
    ('favicon-dark.svg',        512),
    ('wordmark-light.svg',     1600),
    ('wordmark-dark.svg',      1600),
    ('social-card-light.svg',  1280),
    ('social-card-dark.svg',   1280),
    ('banner-light.svg',       1500),
    ('banner-dark.svg',        1500),
]
for name, w in jobs:
    cairosvg.svg2png(url=f'svg/{name}', write_to=f'png/{name[:-4]}.png', output_width=w)
"
```

---

<!-- markdownlint-disable-next-line MD036 -->
*Vol · I  ·  Ed · MMXXVI*
