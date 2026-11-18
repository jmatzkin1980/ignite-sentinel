# Themes

A theme controls how `/dashboard` and `/view` look: colours for light and dark mode, the meaning of each colour (which generates the legend on every page), typography and provenance. This page is for the person who customizes it, such as a developer or an admin applying a client palette or a corporate font. If you only read pages, you need just one thing: the `--theme` option, described in [Artifact views](15-artifact-views.md) and [Dashboard](14-dashboard.md).

The repository ships exactly one theme, `neutral`. Your own themes live on your machine and never enter git.

## Choose a theme

```bash
/dashboard --theme neutral
/view ACME_PORTAL --artifact prd --theme acme
/view ACME_PORTAL --artifact prd --theme C:\path\to\acme.json
```

`--theme` takes a built-in name, a local theme name, or the path to a theme JSON.

A theme **name** is looked up in this order:

1. **Built-in names** (`neutral`) always resolve to the repository theme, in any letter case. A local theme with the same name, in any letter case (`Neutral.json`), is ignored and `/doctor` warns about it. Names may contain only letters, digits, `-` and `_`.
2. **`/view` only:** `workspaces/<PROJECT_ID>/.sentinel/themes/<name>.json`, a theme for one workspace. The workspace `.gitignore` already excludes `.sentinel/`.
3. **`~/.ignite/themes/<name>.json`**, your personal themes. The environment variable `IGNITE_THEMES_DIR` **replaces** that folder (use an absolute path; a relative one resolves against the current directory).

`/dashboard` looks only at the personal folder (step 3), because it spans several workspaces and has no workspace folder.

**What applies when you pass nothing:**

| Command | Order |
|---|---|
| `/view` | `--theme`, then `theme:` in the workspace `sentinel.config.yaml`, then `neutral`. A configured theme that fails to load falls back to `neutral` with a warning; a bad `--theme` is an error. |
| `/dashboard` | `neutral`. It does not read the workspace config. |

The theme also colours the readiness and diagrams views. The colour legend has labels in English and Spanish.

## Create a theme

1. Copy `neutral.json`. In a clone it is `sentinel/themes/neutral.json`; in an installed package it is in the package's `sentinel/themes/` folder. Keep every key: `name`, `label`, `procedencia`, `tipografia`, `tokens.light`, `tokens.dark`, `semantica`.

   > [!NOTE]
   > Some JSON keys are in Spanish: `procedencia` (provenance), `tipografia` (typography), `semantica` (semantic roles) and `isotipo` (logo). Keep them as they are.

2. Change the token values (`#RRGGBB`) and the labels. Each role in `semantica` names the tokens it uses, and the legend is generated from it, so every colour on the page has a stated meaning.
3. Fill `procedencia`: where the palette comes from and who approved it. A theme without it still loads, but `/doctor` reports a warning.
4. Validate it:

   ```bash
   python -m sentinel /doctor
   ```

   `/doctor` lists every local theme under **user-local themes**. It checks `~/.ignite/themes` and `workspaces/*/.sentinel/themes` under the root you run it on.

The validator rejects a missing token, a colour that is not `#RRGGBB`, token names or font lists that could inject CSS, and any external reference (`http://`, `url(`, `//`). Themes are local-first.

### Choose it, do not extract it

Pick a theme deliberately for the audience. Do not extract colours from a prototype or a client's site at run time. A theme is reviewed data with provenance, so the same artifact always renders the same way, and nothing confidential is guessed or copied by a tool.

### Without a logo

There is no logo slot to fill: `isotipo` stays `null`, and the top bar shows the product name as text. That is deliberate.

## Embed fonts

A local theme may embed `.woff2` fonts. They become `data:` URIs inside the page, so a view still makes no network requests.

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

- **Files:** the `.woff2` files and the licence text (`OFL.txt`) sit next to the theme JSON as plain files: no sub-folders, no symlinks. A file must really be a woff2 font, and each one is limited to 1.5 MB.
- **Licence:** use fonts whose licence allows embedding. Heebo, Open Sans and Roboto are under the SIL Open Font License (OFL), and the licence file must travel with them.
- **Page size:** fonts are embedded in every page, so keep to the weights you use.

## Next

- [Artifact views](15-artifact-views.md) and [Dashboard](14-dashboard.md): where the theme applies.
- [Install: choose your path](06-installation-vscode.md): set up the surface you work on.
