from app.db.session import SessionLocal
from app.seed import seed_demo


def main() -> None:
    with SessionLocal() as db:
        seed_demo(db)
    print("Demo data ready.")


if __name__ == "__main__":
    main()
