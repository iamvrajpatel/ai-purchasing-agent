from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.demo_data import seed_demo_data


def _safe_database_url() -> str:
    value = get_settings().database_url
    if "@" not in value:
        return value
    prefix, rest = value.split("@", 1)
    if ":" not in prefix:
        return value
    return prefix.rsplit(":", 1)[0] + ":***@" + rest


def reset_demo_database() -> None:
    try:
        print("Dropping existing database schema...")
        Base.metadata.drop_all(bind=engine)
        print("Creating database schema...")
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            print("Loading demo purchasing data...")
            summary = seed_demo_data(db)
        finally:
            db.close()
    except OperationalError as exc:
        print("Could not connect to PostgreSQL.")
        print(f"Configured DATABASE_URL: {_safe_database_url()}")
        print("Start PostgreSQL and verify the database/user/password before running this reset command.")
        print("Example: docker compose up -d postgres")
        raise SystemExit(1) from exc
    print(
        "Demo database ready: "
        f"{summary['products']} products, "
        f"{summary['warehouses']} warehouses, "
        f"{summary['suppliers']} suppliers, "
        f"{summary['supplier_products']} supplier-product rows, "
        f"{summary['recommendations']} recommendations."
    )


if __name__ == "__main__":
    reset_demo_database()

