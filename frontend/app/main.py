from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import agent, backend, dashboard, purchase_orders, recommendations

app = FastAPI(title="AI Purchasing Agent")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(backend.router)
app.include_router(dashboard.router)
app.include_router(recommendations.router)
app.include_router(agent.router)
app.include_router(purchase_orders.router)


@app.get("/health")
def health():
    return {"status": "ok"}

