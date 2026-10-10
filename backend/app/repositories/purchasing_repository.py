from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AgentRun,
    ApprovalRequest,
    Product,
    PurchaseOrder,
    PurchaseRecommendation,
    PurchasingBudget,
    Warehouse,
)


class PurchasingRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_product(self, product_id: int) -> Product | None:
        return self.db.get(Product, product_id)

    def list_products(self) -> list[Product]:
        return list(self.db.scalars(select(Product).order_by(Product.sku)))

    def get_warehouse(self, warehouse_id: int) -> Warehouse | None:
        return self.db.get(Warehouse, warehouse_id)

    def list_warehouses(self) -> list[Warehouse]:
        return list(self.db.scalars(select(Warehouse).order_by(Warehouse.name)))

    def get_recommendation(self, recommendation_id: int) -> PurchaseRecommendation | None:
        return self.db.scalar(
            select(PurchaseRecommendation)
            .options(selectinload(PurchaseRecommendation.product), selectinload(PurchaseRecommendation.warehouse))
            .where(PurchaseRecommendation.id == recommendation_id)
        )

    def list_recommendations(self) -> list[PurchaseRecommendation]:
        return list(
            self.db.scalars(
                select(PurchaseRecommendation)
                .options(selectinload(PurchaseRecommendation.product), selectinload(PurchaseRecommendation.warehouse))
                .order_by(PurchaseRecommendation.created_at.desc())
            )
        )

    def current_budget(self, warehouse_id: int, budget_period: str) -> PurchasingBudget | None:
        return self.db.scalar(
            select(PurchasingBudget).where(
                PurchasingBudget.warehouse_id == warehouse_id,
                PurchasingBudget.budget_period == budget_period,
            )
        )

    def lock_current_budget(self, warehouse_id: int, budget_period: str) -> PurchasingBudget | None:
        return self.db.scalar(
            select(PurchasingBudget)
            .where(PurchasingBudget.warehouse_id == warehouse_id, PurchasingBudget.budget_period == budget_period)
            .with_for_update()
        )

    def open_purchase_orders(self, product_id: int, warehouse_id: int) -> list[PurchaseOrder]:
        from app.models import PurchaseOrderItem

        return list(
            self.db.scalars(
                select(PurchaseOrder)
                .join(PurchaseOrderItem)
                .options(selectinload(PurchaseOrder.items))
                .where(
                    PurchaseOrderItem.product_id == product_id,
                    PurchaseOrder.warehouse_id == warehouse_id,
                    PurchaseOrder.status.in_(["OPEN", "EXECUTED", "CONFIRMED"]),
                )
                .order_by(PurchaseOrder.expected_delivery_date)
            )
        )

    def purchase_order_by_idempotency(self, idempotency_key: str) -> PurchaseOrder | None:
        return self.db.scalar(
            select(PurchaseOrder).options(selectinload(PurchaseOrder.items)).where(PurchaseOrder.idempotency_key == idempotency_key)
        )

    def purchase_orders_for_recommendation(self, recommendation_id: int) -> list[PurchaseOrder]:
        return list(
            self.db.scalars(
                select(PurchaseOrder)
                .options(selectinload(PurchaseOrder.items))
                .where(PurchaseOrder.source_recommendation_id == recommendation_id)
            )
        )

    def agent_run(self, run_id: int) -> AgentRun | None:
        return self.db.scalar(
            select(AgentRun)
            .options(
                selectinload(AgentRun.tool_calls),
                selectinload(AgentRun.events),
                selectinload(AgentRun.validations),
            )
            .where(AgentRun.id == run_id)
        )

    def approvals(self) -> list[ApprovalRequest]:
        return list(self.db.scalars(select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())))

    def approvals_for_run(self, run_id: int) -> list[ApprovalRequest]:
        return list(self.db.scalars(select(ApprovalRequest).where(ApprovalRequest.agent_run_id == run_id).order_by(ApprovalRequest.id)))

    def approved_approvals_for_run(self, run_id: int) -> list[ApprovalRequest]:
        return list(
            self.db.scalars(
                select(ApprovalRequest)
                .where(ApprovalRequest.agent_run_id == run_id, ApprovalRequest.status == "APPROVED")
                .order_by(ApprovalRequest.id)
            )
        )

    def pending_approval_for_run(self, run_id: int) -> ApprovalRequest | None:
        return self.db.scalar(select(ApprovalRequest).where(ApprovalRequest.agent_run_id == run_id, ApprovalRequest.status == "PENDING"))

    def pending_approvals_for_run(self, run_id: int) -> list[ApprovalRequest]:
        return list(self.db.scalars(select(ApprovalRequest).where(ApprovalRequest.agent_run_id == run_id, ApprovalRequest.status == "PENDING")))

    @staticmethod
    def budget_period_for(day: date) -> str:
        return day.strftime("%Y-%m")
