from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailySale, DemandForecast


class ForecastService:
    def __init__(self, db: Session):
        self.db = db

    def forecasts(self, product_id: int, warehouse_id: int, start_date: date, end_date: date) -> list[DemandForecast]:
        return list(
            self.db.scalars(
                select(DemandForecast)
                .where(
                    DemandForecast.product_id == product_id,
                    DemandForecast.warehouse_id == warehouse_id,
                    DemandForecast.forecast_date >= start_date,
                    DemandForecast.forecast_date <= end_date,
                )
                .order_by(DemandForecast.forecast_date)
            )
        )

    def sales_history(self, product_id: int, warehouse_id: int, start_date: date, end_date: date) -> list[DailySale]:
        return list(
            self.db.scalars(
                select(DailySale)
                .where(
                    DailySale.product_id == product_id,
                    DailySale.warehouse_id == warehouse_id,
                    DailySale.sales_date >= start_date,
                    DailySale.sales_date <= end_date,
                )
                .order_by(DailySale.sales_date)
            )
        )

    def demand_anomaly_ratio(self, product_id: int, warehouse_id: int, days: int = 7) -> float:
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        forecast_total = sum(row.expected_quantity for row in self.forecasts(product_id, warehouse_id, start_date, end_date))
        sales_total = sum(row.units_sold for row in self.sales_history(product_id, warehouse_id, start_date, end_date))
        if forecast_total == 0:
            return 0 if sales_total == 0 else 999
        return sales_total / forecast_total

