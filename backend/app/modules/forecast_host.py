"""FarmNex glue for the AI forecaster connector (docs/integration/ai-forecaster.md).

Loaded by `wiring.py` when ENABLE_FORECAST=true. The router is imported inside `mount` (not at the
top) so a bad setting only disables the forecaster, never the backend.
"""

from __future__ import annotations

import os

from fastapi import Depends, FastAPI

from app.api.dependencies.current_user import get_current_user


def mount(app: FastAPI) -> None:
    missing = [n for n in ("FORECASTER_URL", "FORECASTER_API_KEY") if not os.getenv(n, "").strip()]
    if missing:
        raise RuntimeError(f"{' and '.join(missing)} not set; the forecaster stays unmounted.")

    from .forecast import router  # imported here on purpose (shared rule 3)

    # Every forecast route (also /meta and /health) needs a logged-in user.
    app.include_router(router, prefix="/api/v2", dependencies=[Depends(get_current_user)])
