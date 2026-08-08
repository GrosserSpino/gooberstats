# GooberStats

Public, static Goober Dash analytics for GitHub Pages.

## Update data

```powershell
python scripts/build_site_data.py --tools-root ../goober-dash-tools-sync
```

The exporter selects the latest fully completed monthly leaderboard and writes its top 50 to `docs/data/biggest-winners.json`. Player profiles are copied from `Goober Profiles/public/data`.

## Monthly background

The optional file `docs/assets/monthly-background.webp` is used behind Biggest Winners. The race generator can replace this stable file after rendering; HTML and CSS need no monthly change.

GitHub Pages should publish `main` / `docs`. Data updates commit directly to the repository, so no Actions artifact storage is used.
