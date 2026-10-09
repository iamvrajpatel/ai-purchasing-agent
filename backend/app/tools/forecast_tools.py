from datetime import date

from sqlalchemy.orm import Session

from app.services.forecast_service import ForecastService


class ForecastTools:
    def __init__(self, db: Session):
        self.service = ForecastService(db)

    def get_demand_forecast(self, product_id: int, warehouse_id: int, start_date: str, end_date: str) -> dict:
        rows = self.service.forecasts(product_id, warehouse_id, date.fromisoformat(start_date), date.fromisoformat(end_date))
        return {"forecasts": [{"date": row.forecast_date.isoformat(), "expected_quantity": row.expected_quantity} for row in rows]}

    def get_sales_history(self, product_id: int, warehouse_id: int, start_date: str, end_date: str) -> dict:
        rows = self.service.sales_history(product_id, warehouse_id, date.fromisoformat(start_date), date.fromisoformat(end_date))
        return {"sales": [{"date": row.sales_date.isoformat(), "units_sold": row.units_sold} for row in rows]}

