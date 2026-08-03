# Teaching Website Prototype

This folder is the first website layer for the UK 2050 energy model.

## Structure

- `app.py`: Streamlit interface for classroom-style scenario exploration.
- `service.py`: Thin service layer that calls the existing demand, supply, `PowerSystem`, and `PowerSystemNoH2` model code.
- `__init__.py`: Makes the folder importable for tests and future app code.

## Run Locally

Install dependencies, then run the prototype:

```bash
uv sync
uv run streamlit run teaching_site/app.py
```

## Design Direction

The first screen is the simulator itself, not a landing page. The UI exposes only the core teaching controls:

- renewable capacity
- model variant: hydrogen or no hydrogen
- hydrogen storage and conversion capacity
- medium-term storage
- DAC capacity
- calculated minimum gas + CCS backup capacity
- demand mode and optional imports

The current service layer is intentionally framework-light. A future FastAPI or React interface can reuse `teaching_site.service` without duplicating model logic.
