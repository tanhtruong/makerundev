---
name: makerundev
description: Self-hosted running analytics, drawn as a 400 m track seen from the stands.
colors:
  background: "#fafaf8"
  foreground: "#1b1d1f"
  muted: "#f0efeb"
  muted-foreground: "#5f6367"
  border: "#e3e1dc"
  rule: "#1b1d1f"
  input: "#c9c6bf"
  accent: "#f0efeb"
  tartan: "#c8462b"
  tartan-foreground: "#ffffff"
  lane: "#c8462b"
  series-fitness: "#2a78d6"
  series-fatigue: "#1baf7a"
  series-form: "#6250d6"
typography:
  display:
    fontFamily: "Barlow Condensed, Barlow Semi Condensed, ui-sans-serif, system-ui, sans-serif"
    fontSize: "2.5rem"
    fontWeight: 700
    lineHeight: 1
  wordmark:
    fontFamily: "Barlow Condensed, Barlow Semi Condensed, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    letterSpacing: "0.025em"
  body:
    fontFamily: "Barlow, ui-sans-serif, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "tnum"
  figure:
    fontFamily: "Barlow Semi Condensed, Barlow, ui-sans-serif, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 500
    fontFeature: "tnum"
  section:
    fontFamily: "Barlow Condensed, Barlow Semi Condensed, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.25
  headline-figure:
    fontFamily: "Barlow Condensed, Barlow Semi Condensed, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.875rem"
    fontWeight: 700
    lineHeight: 1
  label:
    fontFamily: "Barlow Semi Condensed, Barlow, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    letterSpacing: "0.08em"
  control:
    fontFamily: "Barlow, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 500
  secondary:
    fontFamily: "Barlow, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
rounded:
  md: "4px"
spacing:
  cell: "10px"
  gutter-mobile: "16px"
  gutter-desktop: "40px"
  section: "24px"
components:
  button:
    backgroundColor: "{colors.background}"
    textColor: "{colors.foreground}"
    typography: "{typography.control}"
    rounded: "{rounded.md}"
    padding: "0 12px"
    height: "32px"
  button-hover:
    backgroundColor: "{colors.accent}"
  top-bar:
    backgroundColor: "{colors.tartan}"
    textColor: "{colors.tartan-foreground}"
    height: "56px"
  table-head:
    textColor: "{colors.muted-foreground}"
    typography: "{typography.label}"
    padding: "0 10px"
    height: "40px"
  table-cell:
    typography: "{typography.body}"
    padding: "10px"
  table-row-hover:
    backgroundColor: "{colors.accent}"
  lane-bar:
    backgroundColor: "{colors.lane}"
    height: "8px"
  input:
    backgroundColor: "{colors.background}"
    textColor: "{colors.foreground}"
    typography: "{typography.body}"
    rounded: "0"
    padding: "0 10px"
    height: "32px"
  input-invalid:
    backgroundColor: "{colors.muted}"
---

# Design System: makerundev

## Overview

**Creative North Star: "The Track From the Stands"**

The React app is a 400 m athletics track seen from the stands. A tartan red top bar carries the wordmark and the navigation in lane white, with a white lane line drawn under it. Below it the ground is lane white in light mode and a floodlit night track in dark mode. Everything else is ink: dense tables, hairline rules and aligned tabular figures. Every run is a lane. Its length is drawn true to scale from a black start line.

The system is flat, dense and quantitative. One superfamily, Barlow, does all the typographic work and ranks by width and weight instead of by size jumps. Tartan red has one job. It marks where you are (the top bar) and how far a run went (the lane bar). It never decorates, never fills a button and never signals status.

State is shown by form as well as colour. The active page has an underline, and a disabled control has a dashed border. A reader who cannot tell red from grey loses nothing.

**Key Characteristics:**
- Tartan top bar with a 3px lane-white line under it, then a 6px band of tartan.
- One accent with one job; the rest of the page is three ink values on a warm off-white ground.
- Hairline 1px rules between rows and a heavier rule under table headers.
- Barlow superfamily: Condensed for headings, Semi Condensed for figures and labels, regular width for prose.
- Tabular figures everywhere, numbers right-aligned in their columns.
- Square, flat, shadowless surfaces; a 4px radius only on buttons.

## Colors

A warm off-white ground and near-black ink, with tartan red kept for place and distance. Dark mode swaps the ground for a night-track charcoal and keeps the top bar the same red.

### Primary
- **Tartan Red**: the top bar's fill and the text selection highlight. It stays the same red in both modes, so the bar reads as the same track day or night.
- **Lane Red**: the fill of the lane bar. It matches Tartan Red in light mode and brightens to #e5694a in dark mode, so a thin 8px bar holds up against the charcoal ground.

### Neutral
- **Lane White Ground** (background): the page ground. Dark mode: #121416, the floodlit night track.
- **Track Ink** (foreground): body text, headings and figures. Dark mode: #eceae6.
- **Start Line Ink** (rule): the 1px rule under table headers and the 2px start line of the lane column. It is the same value as Track Ink, so rules carry full ink weight.
- **Stand Grey** (muted-foreground): secondary text such as start times, counts, column labels and the paging range. Dark mode: #a3a6a9.
- **Infield Wash** (muted / accent): loading placeholders, row hover and the fill of an invalid field. Dark mode: muted #1c1f22, accent #1f2326.
- **Hairline** (border): the 1px divider between rows and around empty and error states. Dark mode: #2a2e32.
- **Field Edge** (input): disabled outline borders and the scrollbar thumb. Dark mode: #3a3f44.
- **Lane White** (tartan-foreground): text, underlines and the lane line on the tartan bar.

### Series
Chart lines take hues from a validated categorical palette, stepped separately for each mode: **Fitness** blue (#2a78d6, dark #3987e5), **Fatigue** aqua (#1baf7a, dark #199e70) and **Form** violet (#6250d6, dark #9085e9). Fitness and fatigue share a chart and pass the colour-blind and normal-vision separation checks in both modes. Aqua sits under 3:1 on the light ground, so a chart with two or more series also carries a legend and a direct label at each line end, and the same numbers are in the table below the charts. A chart with one series, such as Form, needs neither: its caption names it.

### Named Rules
**The One Job Rule.** Tartan red marks where you are and how far you went: the top bar, the lane bar and the text selection. Never use it for buttons, links, badges, status or decoration.

**The Three Inks Rule.** Text uses Track Ink or Stand Grey, and rules use Hairline or Start Line Ink (the same value as Track Ink), so the page reads in three ink values. Field Edge is kept for disabled borders and the scrollbar only. Any other grey is drift.

## Typography

**Display Font:** Barlow Condensed (with Barlow Semi Condensed, then system sans)
**Body Font:** Barlow (with system sans)
**Label/Mono Font:** Barlow Semi Condensed for figures and column labels

**Character:** one grotesque superfamily, bundled with the app and never fetched from a CDN, ranked by width. Narrow and bold reads as a stadium board; regular width reads as notes.

### Hierarchy
- **Display** (Barlow Condensed 700, 2.5rem, line-height 1): the page heading, such as Activities.
- **Wordmark** (Barlow Condensed 700, 1.25rem, tracking 0.025em): makerundev, lower case, in the top bar only.
- **Body** (Barlow 400, 15px, line-height 1.45, tabular figures): table text, prose and navigation (navigation at weight 500). Prose is capped at 65ch.
- **Figure** (Barlow Semi Condensed 500, 15px, tabular): every measured number in a table, right-aligned.
- **Section** (Barlow Condensed 700, 1.5rem): a heading inside a page, such as Performance, last 6 weeks.
- **Headline figure** (Barlow Condensed 700, 1.875rem, line-height 1): the single number of a figures row, such as fitness or VDOT.
- **Label** (Barlow Semi Condensed 600, 0.75rem, tracking 0.08em, uppercase): table column headers and the names in a figures row, in Stand Grey.
- **Control** (Barlow 500, 0.875rem): button text.
- **Secondary** (Barlow 400, 0.875rem, Stand Grey): the date and the heart rate folded under the name and the pace on phones. A lead line, such as an empty state's "No activities yet.", is Body at weight 600, not a larger size.

### Named Rules
**The Width Ranks Rule.** Hierarchy comes from width and weight within Barlow, not from a second family or large size jumps. Condensed for headings, Semi Condensed for figures and labels, regular width for reading.

**The Tabular Figures Rule.** The body sets `font-variant-numeric: tabular-nums`. Numbers that are compared down a column are right-aligned and set in Figure, so the digits line up.

## Layout

Content sits in a centred column up to 1400px wide, with a 16px gutter on phones and 40px from the `sm` breakpoint (640px). The page block has 32px of vertical padding on phones and 40px from `sm`. The heading row sits 24px above the import form, with the heading on the left and the count baseline-aligned at the right, and the form sits 24px (the section spacing) above the table. Paging sits 20px below the table: range and total at the left, Previous and Next at the right.

Tables are dense. Cells have 10px padding, headers are 40px tall, and text never wraps except the activity name on phones. Columns drop out by width rather than the table turning into cards. Below `sm` the date folds under the name and heart rate folds under pace. Below `md` (768px) sport, moving time and climb are hidden. The lane column takes about a third of the table width.

The top bar is 56px tall from `sm`. On phones the wordmark sits above a wrapping row of nav links.

## Elevation & Depth

Flat. There are no shadows anywhere. Depth comes from the tartan bar against the ground, from rules, and from the Infield Wash on row hover. Overlays, if they come, should carry a rule border before they reach for a shadow.

### Named Rules
**The Flat Track Rule.** Surfaces sit on the ground. A row is marked by its hairline, a header by its ink rule, and a hovered row by Infield Wash, never by a lift.

## Shapes

Square by default. Rows, tables, placeholders, lane bars and the top bar have no radius. Only buttons have gently softened corners (4px). Strokes come in a fixed set: 1px hairlines between rows, a 1px ink rule under headers, a 2px start line at the left of the lane column, a 2px underline for the active nav link, and the 3px lane-white line under the top bar.

**The Lane Line Rule.** A border or rule heavier than 1px is a track marking: the start line, the lane line under the bar, or the active-lane underline. Do not add heavy borders or rules for emphasis anywhere else. The 2px focus outline is not a border and is exempt.

## Components

### Buttons
Quiet and functional. They sit beside data and never outshout it. There is no filled button; every button is outlined.
- **Shape:** gently softened corners (4px).
- **Outline (the only variant):** a 1px Start Line Ink border on the ground, 32px tall with 12px side padding, the one size used for paging and retry. Hover fills with Infield Wash.
- **Disabled:** the border turns dashed and Field Edge-grey, and the text turns Stand Grey, so the state reads by form as well as colour.
- **Focus:** a 2px ring in Track Ink, offset 2px (global).

### Navigation
- **Style:** the tartan top bar, with the wordmark and links in Lane White at Body size, weight 500, spaced 24px apart from `sm`.
- **States:** the active link carries a 2px Lane White underline. Hover shows the same underline at 60%. Focus outlines are Lane White on the bar.
- **Mobile:** the links wrap under the wordmark, spaced 20px apart.
- **Lane line:** the bar ends in a 3px Lane White line and then a 6px band of tartan.

### Data table
- **Header row:** Label type in Stand Grey, 40px tall, with a 1px Start Line Ink rule under it. It has no hover. Numeric headers are right-aligned over their figures; the lane column is headed "Distance", right-aligned over the distance figure, and the bar carries no label of its own.
- **Rows:** 1px Hairline dividers, 10px cell padding and Infield Wash on hover over 150ms. The whole row is the link target, through the name link stretched across the row. The link underlines on hover.
- **Figures:** right-aligned in Figure type. Dates are semibold with the time in Stand Grey beside them.

### Lane bar (signature)
The run's distance drawn true to scale. A 2px Start Line Ink start line runs down the left of the column. From it, a square-ended 8px Lane Red bar extends to `distance / longest distance on the page` of the track width. The distance figure sits at the right of the track on desktop and above the bar on phones. The bar is decorative to assistive technology, and the figure carries the value.

**The True Length Rule.** A lane bar's length is the exact ratio to the page's longest run. Never round its ends, add a gradient, a track background or a minimum stub, or scale it to anything other than distance.

### Inputs and labels
- **Label:** Barlow 500 at 0.875rem in Track Ink, above its field.
- **Field:** 32px tall, square, a 1px Start Line Ink border on the ground, with 10px side padding and Body type. A form sits in a column at most 448px wide, with its message and its outline button under the field.
- **Invalid:** the field keeps its solid border and fills with Infield Wash. The message sits under it in Track Ink at 0.875rem, linked to the field as its description. A dashed border always means disabled, never invalid.

### Stat list
Up to four figures in a row (two on phones), each a Label above its value in Barlow Semi Condensed 600 at 1.25rem. Its line of prose, such as how the last sync ended, follows in Stand Grey. There are no boxes, borders or dividers around the figures.

### Status notice
A notice that confirms an action, such as "Key saved.", is a line of Body text in Track Ink between Hairline rules above and below. It carries `role="status"`, has no colour or icon, and stays until the next action replaces it.

### Figures row
A row of headline numbers between Hairline rules above and below: a Label over a Headline figure, with an optional Secondary line under it, such as the effort a VDOT comes from. Four across from `sm`, two on phones. A figure that cannot be computed shows its reason in Stand Grey Body text instead of a number.

### Range switch
A row of plain text links in Stand Grey, such as 90 days, 180 days, 365 days, All. The chosen one turns Track Ink with a 2px ink underline, like the active nav link, and the choice lives in the URL.

### Line chart
- **Marks:** 2px series lines with no dots; a hovered day gets a dot on each line.
- **Axes:** no axis lines or tick marks. The value axis shows only its ends (and zero when it crosses zero) in Stand Grey, with Hairline grid lines at those values. The scale comes from the API, never from the chart library's auto-scaling. The first and last dates sit under the plot.
- **Labels:** with two or more series, a legend above and a direct label at each line's end; the upper series' label sits above the lower one's. A single series is named by the caption alone.
- **Hover:** a 1px ink crosshair and a tooltip with a 1px Start Line Ink border on the ground, listing the day and every value, the series named in Stand Grey with a short line in its colour and the figure in Track Ink.
- **Zero:** a chart that crosses zero draws it as a 1px Start Line Ink rule.

### Loading, empty and error states
- **Loading:** eight placeholder rows of Infield Wash blocks, square, under an ink top rule, with no shimmer.
- **Empty and error:** a block bounded by Hairline rules above and below, with plain-text guidance and inline links in Track Ink. Error offers an outline "Try again" button.

### Import form
The first block on the activity list, bounded by Hairline rules above and below like an empty state. "Import activities" is the lead line (Body at weight 600) with the accepted formats under it in Secondary type. "Choose files" is the outline button, a label for a visually hidden file input that draws the input's focus ring, with the chosen file name or count beside it in Secondary type. The Import button sits at the right, disabled until files are chosen and while they upload.
- **Results:** one row per file, in the order sent, under a 1px Start Line Ink rule with Hairline dividers, like a table without a header. The file name is at the left, linked to its activity when there is one. The outcome is at the right in words: "Imported" and "Already imported" in Stand Grey, a failure's reason in Track Ink, so a failure stands out by weight of ink, never by red.
- **Failure:** when the request itself fails, an error block under the form says why, in the server's words or "the server could not be reached", with an outline "Try again" button that sends the same files again.

## Do's and Don'ts

### Do:
- **Do** keep tartan red to the top bar, the lane bar and text selection (The One Job Rule).
- **Do** set every compared number in Figure type, right-aligned and tabular.
- **Do** show state by form: an underline for the active nav link and a dashed border for a disabled button.
- **Do** separate rows with 1px Hairline rules and close a header with the 1px ink rule.
- **Do** draw a quantity as a square bar from a start line, at its exact ratio to the page's longest run.
- **Do** hide lower-priority columns on narrow screens rather than turning a table into cards.

### Don't:
- **Don't** fill buttons with any colour, or tint links, badges or status messages with tartan or lane red; buttons are outlined.
- **Don't** add box shadows or lifts; the system is flat.
- **Don't** introduce a second type family; rank within Barlow by width and weight.
- **Don't** round the lane bar or table surfaces; only buttons take the 4px radius.
- **Don't** use borders or rules heavier than 1px except for the track markings named in The Lane Line Rule; the 2px focus outline is exempt.
