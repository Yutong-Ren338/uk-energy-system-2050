# Source images for build_svg.py

## Currently used: fake-data schematic charts

`build_svg.py` currently embeds `fake_*.png` &mdash; illustrative charts with **no
real numbers**, generated from synthetic data by
[`../../fake_data_plots.ipynb`](../../fake_data_plots.ipynb). Real screenshots
(see below) stayed too small to read once shrunk into these panels; these instead
show large, legible axis labels that make clear what *type* of data each panel
represents, without pretending to show real results.

| file | used for (box) |
|---|---|
| `fake_weather.png` | Step 1 &mdash; weather reanalysis (noisy capacity-factor-like signal) |
| `fake_demand.png` | Step 1 &mdash; demand + CB7 projections (seasonal wave) |
| `fake_cost.png` | Step 1 &mdash; DESNZ technology cost data (declining cost curve) |
| `fake_netsupply.png` | Step 2 &mdash; daily net supply&minus;demand (noisy signal around a zero baseline) |
| `fake_timeseries.png` | Step 4 &mdash; the enlarged Time series panel (storage level + multi-channel energy flow) |

To change one: edit the corresponding cell in `fake_data_plots.ipynb`, re-run it,
then re-run `../build_svg.py`.

## Kept for reference, no longer used: real screenshots

The `final_*.png` files below are genuine model outputs/screenshots from an earlier
version of the diagram. `build_svg.py` no longer reads them (the panels they filled
were unreadable at this diagram's thumbnail size), but they're kept in case they're
useful again later (e.g. in a full-size figure elsewhere).

| file | was used for (box) | where it came from |
|---|---|---|
| `final_weather.png` | Step 1 &mdash; weather reanalysis | Cropped from `nbs/Wind_Reader.ipynb`'s `plot_ninja_2025_wind_power` output (legend cropped off) |
| `final_demand.png` | Step 1 &mdash; demand + CB7 projections | `output/CB7.png` (Seventh Carbon Budget balanced-pathway removals chart) |
| `final_cost.png` | Step 1 &mdash; DESNZ technology cost data | Cropped from `nbs/edac_lcor_sensitivity.ipynb` (E-DAC LCOR vs capacity factor) |
| `final_netsupply.png` | Step 2 &mdash; daily net supply&minus;demand | Cropped from a live screenshot of the "Renewable and nuclear supply minus demand" chart in the running `teaching_site/app.py` Streamlit app |
| `final_timeseries.png` | Step 4 &mdash; time series | Cropped from `nbs/no_h2_power_system_demo.ipynb`'s `plot_simulation_results` output |
| `final_annual.png` | Step 4 &mdash; annual metrics (chart version; now a bullet point instead) | Cropped from `nbs/compare_h2_vs_no_h2.ipynb` (net CO2 removed, E-DAC + LTDAC, vs renewable capacity) |
| `final_scenario.png` | Step 4 &mdash; scenario search (chart version; now a bullet point instead) | `output/cost.png` (best feasible cost at each renewable capacity, bisection-search optimum starred) |
| `final_app.png` | Step 4 &mdash; teaching app (chart version; now a bullet point instead) | Cropped from the same live Streamlit app screenshot as `final_netsupply.png` (sidebar + header) |

## Regenerating a screenshot-based image

`final_netsupply.png` and `final_app.png` came from a live screenshot of the
Streamlit app. To retake it:

```bash
# from repo root, with the app's deps installed in .venv
./.venv/Scripts/python.exe -m streamlit run teaching_site/app.py --server.headless true --server.port 8532

# then, with playwright installed (pip install playwright) and a system Edge/Chrome:
python - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 2200, "height": 1100})
    page.goto("http://localhost:8532", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(8000)  # let the first simulation run finish
    page.screenshot(path="app_screenshot.png")
    browser.close()
PY
```

Then crop the region you want (e.g. with Pillow) into `final_netsupply.png` /
`final_app.png` and re-run `../build_svg.py`.

## Regenerating a notebook-based image

The other images were extracted from already-executed notebook cell outputs
(a `.ipynb` stores each plot as base64 PNG inside the cell's JSON `outputs`).
To pull a fresh one: open the source notebook, find/re-run the relevant cell,
then extract its `image/png` output (e.g. via `json.load` + `base64.b64decode`,
or just save the figure from the notebook UI) and crop as needed.
