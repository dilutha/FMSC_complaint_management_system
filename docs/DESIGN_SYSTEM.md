# Design system — FMSC Cases (USJ branding)

## 1. Sources

| Asset | Source | Notes |
|---|---|---|
| Logo | `https://www.sjp.ac.lk/wp-content/uploads/2020/10/usjp-logo-1.png`, linked as the PNG download on the [official branding page](https://www.sjp.ac.lk/branding-and-visual-identity/) | Copied byte-for-byte into `mobile/assets/branding/usj_logo.png` (identical SHA-256 checksum). It isn't recoloured, cropped or redrawn. |
| Logo palette | Image *"USJP Logo Color Palette"* (`/wp-content/uploads/2020/10/Asset-1.png`) under "Use of Colors" on the official branding page | The HEX, RGB and CMYK values are printed in the image. They were transcribed, not extracted from pixels. |
| Website palette | Image *"USJP Website Color Palette"* (`/wp-content/uploads/2020/10/Asset-2.png`), same page | Transcribed in the same way. |
| Logo rules | [Guidelines for using the SJP logo](https://www.sjp.ac.lk/guidelines-for-using-sjp-logo/) | Use the latest version, use it in full, don't change its colours, and keep its proportions. Place it top left, middle or right. |

The university publishes its colour codes only as images, not as text. The values below are copied from those official images. None of them were sampled or approximated.

## 2. Brand colours (official)

| Token (`UsjColors`) | HEX | RGB | CMYK (as published) | Palette |
|---|---|---|---|---|
| `red` | `#C1282D` | 193, 40, 45 | C17 M98 Y93 K7 | Logo |
| `yellow` | `#F9EB24` | 249, 235, 36 | C5 M0 Y93 K0 | Logo |
| `black` | `#010101` | 1, 1, 1 | C75 M68 Y67 K90 | Logo |
| `maroon` | `#800000` | 127, 20, 22 † | C29 M100 Y100 K38 | Website |
| `blue` | `#314E86` | 49, 78, 134 | C91 M76 Y21 K69 | Website |
| `paleBlue` | `#CBE2F1` | 203, 226, 241 | C19 M4 Y1 K0 | Website |
| `gold` | `#E9AD21` | 233, 173, 33 | C8 M33 Y100 K0 | Website |
| `softYellow` | `#F7D739` | 247, 215, 57 | C4 M11 Y89 K0 | Website |

† The official image gives two inconsistent values for this colour: HEX `#800000` (which is RGB 128, 0, 0) and RGB `127, 20, 22`. The app uses the published HEX value. **This needs confirmation from the university's branding office.**

## 3. Project colours (not university colours)

The neutral and semantic colours below were chosen for this project. They are **not** official USJ brand colours.

| Role | Token | HEX |
|---|---|---|
| Page background | `background` | `#F6F6F7` |
| Card / input surface | `surface` | `#FFFFFF` |
| Borders | `border` | `#D6D6DB` |
| Body text | `textPrimary` | `#1C1C21` |
| Secondary text | `textSecondary` | `#55555F` |
| Success | `success` / `successBg` | `#1E6B34` / `#E3F2E7` |
| Warning | `warning` / `warningBg` | `#7A4E00` / `#FFF3D1` |
| Error | `error` / `errorBg` | `#B3261E` / `#FBE4E2` |
| Info | `info` (official blue) / `infoBg` | `#314E86` / `#E6EEF7` |

## 4. Where each colour is used

The brand colours are used as accents. Most of each screen is neutral.

- **Maroon:** app bar.
- **USJ red:** primary actions (filled buttons, the "New case" button) and the latest timeline step.
- **USJ yellow:** selected states only (filter chips, segmented buttons, navigation indicator). Text on yellow is always dark.
- **Gold:** the left accent bar on the "Is the issue resolved?" prompt.
- **Official blue:** focus rings and the "info" status tone.
- **Neutrals:** all content backgrounds, cards and body text.

## 5. Contrast (WCAG 2.2)

Ratios were computed with the WCAG relative-luminance formula. The AA minimum is 4.5:1 for normal text.

| Pair | Ratio | Result |
|---|---|---|
| White on USJ red (buttons) | 5.82:1 | AA |
| White on maroon (app bar) | 10.95:1 | AAA |
| Dark text on USJ yellow (selected chips) | 13.69:1 | AAA |
| USJ red text on white | 5.82:1 | AA |
| Body text on white | 16.97:1 | AAA |
| Secondary text on background | 6.82:1 | AA |
| Success / warning / error / neutral badges | 5.65 / 6.51 / 5.38 / 7.44 :1 | AA |
| Blue on info background | 6.99:1 | AA |
| **Yellow on white** | **1.24:1** | **Fails.** Never use yellow for text or icons on white. |

## 6. UX principles applied

| Principle | How it is applied |
|---|---|
| Jakob's law | Standard Material patterns throughout: app-bar back button, extended button bottom-right, pull-to-refresh, list → detail. |
| Hick's law | My Cases has only 4 filters. Case type and priority are 2-option segmented controls. |
| Fitts's law | Touch targets are at least 48 dp. The primary action is full width at the end of each form, and "New case" sits in the thumb zone. |
| Miller's law | Forms and the detail screen are split into titled `SectionCard` groups (Summary, Description, Resolution, Attachments, Progress). |
| Visibility of status | Loading, empty, error-with-retry and success states on every screen. The timeline shows progress. Overdue cases get a badge. |
| Error prevention | Attachment type and size are checked on the device before upload, the declaration is required, and a reason is required to reopen or report "problem persists". |
| Recovery | Server field errors appear under the matching field. Failed page loads offer "Try again". |
| Recognition over recall | The reference number can be copied, statuses use plain-language labels, and the solved case shows what was done before asking the user to confirm. |
| WCAG 1.4.1 | Status and priority always show icon and text, never colour alone. Badges expose semantic labels. |
| Focus visibility | Inputs show a 2 px official-blue focus border. |
