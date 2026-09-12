# Palette — "Cold Cathode"

Every colour in every template resolves through CSS custom properties declared
in a `:root` block at the top of that file's `<style>`. There are no colour
literals outside `:root`, so a repaint means editing those values and nothing
else. Names are **roles**, not colours.

## The idea

A cool teal/cyan instrument panel on near-black. Three things carry the look,
and only one of them is hue:

1. **Near-black ground** — `#0d1316` panels on `#06090b`, cool rather than warm.
2. **Monospace throughout** — one font stack for the whole UI, not just the console.
3. **Flat corners** — `--radius-sm` / `--radius` / `--radius-pill` at 2-3px.
   Raise those three values to soften every corner in the UI at once.

The accent is a light blue-teal (`#2ad6ee`). That hue window is the one place
that is far from every status colour (red 350° → green 150°) *and* far from
amber, which matters more than it sounds: because the chrome no longer competes
with the signal, the status lights can be **conventional** green / yellow /
orange / red instead of being bent out of shape to dodge the UI colour.

Prose is a cool neutral (`#dfe7ea`), not tinted with the accent. Two earlier
attempts got this wrong — one made the whole UI violet and read as a recolour,
the other made body text amber, which across a dense dashboard is a dull yellow
wash. The accent belongs on buttons, links, headings and borders; the prose
should stay out of its way.

The two status banners (automation paused, ERP writes disabled) are the one
deliberately warm thing on the page. They are notices, and being the only warm
element is what makes them read as notices.

## Status colours were measured, not chosen by eye

Green / yellow / orange / red are the one thing that could not be picked for
looks: they carry meaning, and red-green colour blindness collapses them.
Candidate sets were scored on CIEDE2000 separation under normal vision plus
simulated deuteranopia and protanopia (Viénot/Brettel/Mollon 1999 matrices),
subject to each colour keeping ≥4.8:1 contrast against the panel and staying
within a hue window that keeps it recognisably itself.

The nearest status sits **31.5 dE** from the teal chrome, so nothing on the
page competes with a status light.

Minimum pairwise separation across all four lights:

| vision | original slate | cold cathode |
|---|---|---|
| normal | 19.7 | **27** |
| deuteranopia | 7.8 | **12** |
| protanopia | 7.1 | **11** |

Roughly a 50% improvement under both forms of colour blindness. It is still
not a large margin — which is why the lights also carry ✓ / ! / × glyphs.
**Colour is the second cue here, not the only one.** If you change a status
colour, re-run the numbers.

`--led-idle` (the "no reading yet" light) is a neutral grey, 29.7 dE from the
teal chrome, so an unknown unit never reads as UI furniture.

## Contrast

All twelve text/background pairs clear 7:1 (WCAG AAA). Under the old palette
three did not: `text-muted` on panel was 5.71, on sunken 6.96, and white on the
accent was 5.17.

| pair | original slate | cold cathode |
|---|---|---|
| text on panel | 11.87 | 14.94 |
| text-muted on panel | 5.71 | **7.25** |
| text-muted on sunken | 6.96 | **7.73** |
| text on accent | 5.17 | **10.38** |
| accent on panel | 2.83 | **10.65** |

**Honest exception:** the three border tokens are low-contrast by design —
1.27, 1.93 and 3.54 against the panel. They are hairlines separating
same-coloured surfaces; at 4.5:1 every panel edge becomes a hard outline. The
original slate palette was 1.41 / 1.93 / 3.07, so these are close to unchanged.
On a near-black ground that is the intended effect, but if the UI feels too
structureless, raise `--border` and `--border-strong` — they are two values.

## Re-running the checks

The scoring code is not committed — it was throwaway analysis. To redo it you
need CIEDE2000, WCAG contrast, and the Viénot dichromat matrices applied in
linear RGB. Feed it the `:root` values from `templates/issues_results.html`.
