#!/usr/bin/env python3
"""Seed 100 clearly labeled mock questions for testing Prelims practice."""

import logging

from app.database import Base, SessionLocal, engine
from app.prelims_demo import seed_demo_questions


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        result = seed_demo_questions(db)
    logging.info(
        "Added %d demo question(s); %d demo question(s) are available. "
        "These are mock questions, not official UPSC PYQs.",
        result["inserted"],
        result["total"],
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
