from app.core.database import SessionLocal
from app.demo_data import seed_demo_data


def seed() -> None:
    db = SessionLocal()
    try:
        seed_demo_data(db)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
    print("Seed data loaded.")

