"""Fill the PostgreSQL database with the cleaned datasets.

Run:  uv run python -m scripts.seed_db

Steps:
  1. clean and validate the CSV files (scripts/clean_data.py)
  2. drop the old tables and create empty ones
  3. insert the jobs and the candidates

The script can be run again at any time: it always starts from an empty database.
"""

from sqlalchemy import text

from app.database import Base, SessionLocal, engine
from app.models import Candidate, Job
from scripts.clean_data import load_clean_data


def main() -> None:
    jobs, candidates = load_clean_data()

    # Start from scratch, so running the script twice does not create duplicates.
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        for row in jobs:
            row["id"] = row.pop("job_id")  # the CSV column is job_id, the table column is id
            db.add(Job(**row))
        for row in candidates:
            row["id"] = row.pop("candidate_id")
            db.add(Candidate(**row))
        db.commit()

        # The ids came from the CSV files, so PostgreSQL's id counters are still at 1.
        # Move them after the highest id, otherwise the next POST would try id 1 again.
        for table in ("jobs", "candidates"):
            db.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), (SELECT MAX(id) FROM {table}))"
            ))
        db.commit()

    print(f"Inserted {len(jobs)} jobs and {len(candidates)} candidates into the database.")


if __name__ == "__main__":
    main()
