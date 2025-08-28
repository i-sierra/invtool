from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import (
    config_ref,
    distributors,
    locations,
    part_distributors,
    part_documents,
    part_types,
    parts,
    purchase_orders,
    reports,
    stock,
    ui_distributor_catalog,
    ui_parts,
    ui_purchase_orders,
    ui_reports,
)

app = FastAPI(title="Inventory Management System")


@app.get("/health")
def health():
    return {"status": "ok"}


# ---- API routers ----
app.include_router(config_ref.router)
app.include_router(distributors.router)
app.include_router(locations.router)
app.include_router(parts.router)
app.include_router(part_distributors.router)
app.include_router(part_documents.router)
app.include_router(part_types.router)
app.include_router(purchase_orders.router)
app.include_router(reports.router)
app.include_router(stock.router)

# ---- UI routers ----
app.include_router(ui_distributor_catalog.router)
app.include_router(ui_parts.router)
app.include_router(ui_purchase_orders.router)
app.include_router(ui_reports.router)

# ---- Static files for UI ----
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
