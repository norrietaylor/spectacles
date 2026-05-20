# spectacles · brand assets

Logo, wordmark, social card, and banner for the `spectacles` repository.
Each asset ships in **light** and **dark** themes, in **SVG** (source) and
**PNG** (rasterized) formats.

`spectacles` is part of a three-tool suite alongside `ch-oracles` (chore
agents) and `chronicles` (evaluation agents). The three tools share an
identical design system, distinguished only by their mark shape and
accent color.

---

## Design system

Modern minimal. Pure geometric mark with a single jewel-tone accent.
No serifs, no rules, no edition marks — clean and confident.

| Aspect       | Spec                                          |
| ------------ | --------------------------------------------- |
| Mark         | Filled triangle, black ink, sapphire dot      |
| Wordmark     | Inter SemiBold (600), lowercase, tight track  |
| Tagline      | Inter Regular (400), lowercase, default track |
| Light surface| `#ffffff`                                     |
| Dark surface | `#0e0e10`                                     |
| Ink (light)  | `#1a1a1a`                                     |
| Ink (dark)   | `#f5f5f5`                                     |
| Accent (light) | `#1e3a8a` (sapphire)                        |
| Accent (dark)  | `#3b5fc9` (sapphire, brightened)            |

The workflow diagram (input → mark → fan-out → outputs) appears only in
the social card and banner, never in the logo.

---

## Files

| File                          | Size          | Use                                |
| ----------------------------- | ------------- | ---------------------------------- |
| `logo-{theme}.svg/png`        | 1024 × 512    | Primary brand mark                 |
| `favicon-{theme}.svg/png`     | 64 × 64       | Browser tabs, app icons            |
| `wordmark-{theme}.svg/png`    | 800 × 400     | Mark + wordmark + tagline lockup   |
| `social-card-{theme}.svg/png` | 1280 × 640    | OG image (GitHub social preview)   |
| `banner-{theme}.svg/png`      | 1500 × 500    | README hero banner                 |

For GitHub theme-aware banner switching in your README:

```markdown
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/png/banner-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="./assets/png/banner-light.png">
  <img alt="spectacles — spec-driven development agents for GitHub Actions" src="./assets/png/banner-light.png">
</picture>
```

---

## Suite-wide

Each tool gets its own jewel:

| Tool         | Mark          | Accent             |
| ------------ | ------------- | ------------------ |
| spectacles   | triangle      | sapphire `#1e3a8a` |
| ch-oracles   | ring          | amethyst `#6b21a8` |
| chronicles   | bars          | ruby `#9f1239`     |

The three accents are deliberately at similar saturation and depth — they
read as a deep-jewel set when shown together.

---

## Typography

[Inter](https://rsms.me/inter/) — open-source, available via Google Fonts,
fontsource, or self-hosted. SVGs fall back to system UI sans when Inter
isn't available; PNGs have Inter baked in.

---

*This system supersedes earlier retro-academic asset sets.*
