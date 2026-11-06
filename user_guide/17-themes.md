# Visual Themes

`/dashboard` and `/view` render with a **theme**: colour tokens for light and dark mode, the meaning of each colour (which generates the legend on every page), typography and provenance. The repository ships exactly one theme, `neutral`. Your own themes (a client palette, a corporate font) live on your machine and never enter git.

## Choosing a theme

```powershell
python -m sentinel /dashboard --theme neutral
python -m sentinel /view PROJECT_ID --artifact prd --theme acme
python -m sentinel /view PROJECT_ID --artifact prd --theme C:\path\to\acme.json
```

A theme **name** is looked up in this order:

1. Built-in names (`neutral`) always resolve to the repo theme. A local theme with the same name is ignored, and `/doctor` warns about it.
2. `/view` only: `workspaces/PROJECT_ID/.sentinel/themes/<name>.json`, a theme for one workspace. The workspace `.gitignore` already excludes `.sentinel/`.
3. `~/.ignite/themes/<name>.json`, your personal themes. Set `IGNITE_THEMES_DIR` to use another folder.

Without `--theme`, `/view` uses `theme:` from the workspace config, then `neutral`. A configured theme that fails to load falls back to `neutral` with a warning. A bad `--theme` is an error.

## Creating a theme

1. Copy the structure of `sentinel/themes/neutral.json`. Keep every key: `name`, `label`, `procedencia`, `tipografia`, `tokens.light`, `tokens.dark`, `semantica`.
2. Change the token values (`#RRGGBB`) and the labels. Each role in `semantica` names the tokens it uses, and the legend is generated from it, so every colour on the page has a stated meaning.
3. Fill `procedencia`: where the palette comes from and who approved it. A theme without it still loads, but `/doctor` reports a warning.
4. Validate it: `python -m sentinel doctor` lists every local theme under **user-local themes**.

The validator rejects:

- a missing token;
- a colour that is not `#RRGGBB`;
- token names or font lists that could inject CSS;
- any external reference (`http://`, `url(`, `//`). Themes are local-first.

### Choose it, do not extract it

Pick a theme deliberately for the audience. Do not extract colours from a prototype or a client's site at run time. A theme is reviewed data with provenance, so the same artifact always renders the same way, and nothing confidential is guessed or copied by a tool.

### Without a logo

There is no logo slot to fill: `isotipo` stays `null`, and the top bar shows the product name as text. That is deliberate. A working document without a brand mark reads as what it is.

## Embedding fonts

A local theme may embed `.woff2` fonts. They become `data:` URIs inside the page, so a view still makes **no network requests**.

```json
"tipografia": {
  "font": "Heebo, system-ui, sans-serif",
  "font_mono": "Consolas, monospace",
  "font_license": "OFL.txt",
  "font_files": [
    { "family": "Heebo", "file": "Heebo-Regular.woff2", "weight": 400, "style": "normal" }
  ]
}
```

- **Files:** the `.woff2` files and the licence text (`OFL.txt`) sit next to the theme JSON, with no sub-folders. Each font is limited to 1.5 MB.
- **Licence:** use fonts whose licence allows embedding. Heebo, Open Sans and Roboto are under the SIL Open Font License (OFL), and the licence file must travel with them.
- **Page size:** the fonts are embedded in every page, so keep to the weights you actually use.
