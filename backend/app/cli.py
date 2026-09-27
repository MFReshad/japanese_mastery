from app.db.session import SessionLocal
from app.seed import seed_demo


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Explicit demo seed (never part of production startup)"
    )
    parser.add_argument("--seed-demo", action="store_true", required=True)
    parser.parse_args()
    with SessionLocal() as db:
        seed_demo(db)
    print("Demo data ready.")


if __name__ == "__main__":
    main()
