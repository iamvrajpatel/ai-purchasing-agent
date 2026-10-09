from fastapi import APIRouter

from app.api.routes import agent, approvals, dashboard, products, purchase_orders, recommendations, suppliers, warehouses

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(dashboard.router)
api_router.include_router(products.router)
api_router.include_router(warehouses.router)
api_router.include_router(suppliers.router)
api_router.include_router(recommendations.router)
api_router.include_router(agent.router)
api_router.include_router(approvals.router)
api_router.include_router(purchase_orders.router)

