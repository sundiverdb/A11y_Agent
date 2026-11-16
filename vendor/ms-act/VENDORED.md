# Vendored: Microsoft Accessibility Considerations Toolkit

A pinned copy of Microsoft's Accessibility Considerations Toolkit (ACT), so the agent keeps
working if the upstream repository changes or disappears. `act.py` reads only from this folder.

| | |
|---|---|
| Upstream | https://github.com/microsoft/Microsoft-Accessibility/tree/main/Accessibility-Considerations-Toolkit |
| Pinned commit | `6d4e52d588eaf2bc79297b3898aa4641d61e574d` (2026-11-11) |
| Copied on | 2026-11-16 |
| License | MIT (`LICENSE.txt`), plus W3C terms for the cognitive topics (`considerations/cognitive-accessibility-sources.LICENSE.md`) and the WCAG reference (`standards/wcag-requirements.LICENSE.md`) |

## What was copied

`README.md`, `LICENSE.txt`, `provenance.json`, and the `considerations/`, `schemas/`,
`methodology/`, `heuristics/` and `standards/` folders, unchanged. Upstream's `tests/`, `scripts/`
and tooling were left out; `provenance.json` still lists some of their fixture paths.

Do not edit these files. Local changes belong in `act.py` or in your own files, so an update can
replace this folder cleanly.

## Updating

This text goes straight into model prompts, so review every update before taking it.

1. Pull upstream into your fork of `microsoft/Microsoft-Accessibility` (or clone upstream).
2. Read the diff of `Accessibility-Considerations-Toolkit/` since the pinned commit above. Watch for
   renamed topic aliases or schema fields: upstream says these are not kept as compatibility aliases.
3. Replace the copied files and folders with the new versions.
4. Update the pinned commit and date in this file.
5. Run `.venv/bin/python -m pytest tests/`.
