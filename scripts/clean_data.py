"""Clean and validate the datasets before they are inserted into the database.

Reads:   data/raw/jobs.csv, data/candidates.csv
Writes:  data/processed/jobs_clean.csv      (rows that are safe to insert)
         data/processed/jobs_rejected.csv   (rows that were dropped + the reason)

Run:  uv run python -m scripts.clean_data

Rules for a job row
-------------------
Fixed automatically:
  - extra spaces are removed from every text value
  - employment type, work mode and category are written in one standard form
  - skill lists are split, trimmed and de-duplicated
  - salary_min and salary_max are swapped when they are in the wrong order
  - an invalid or negative salary becomes "missing" (the job is still kept)
  - filled_positions is limited to the range 0..vacancies
Rejected (the row is not inserted):
  - a required text field is empty
  - unknown employment type or work mode
  - latitude / longitude missing, not a number or out of range
  - no required skills, invalid deadline, vacancies below 1
  - duplicate of an earlier row (same title, employer, location and employment type)
"""

import csv
from datetime import date, time
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RAW_JOBS_FILE = DATA_DIR / "raw" / "jobs.csv"
CANDIDATES_FILE = DATA_DIR / "candidates.csv"
CLEAN_JOBS_FILE = DATA_DIR / "processed" / "jobs_clean.csv"
REJECTED_JOBS_FILE = DATA_DIR / "processed" / "jobs_rejected.csv"

# Standard spelling of the allowed values. The keys are lower-case with "-" instead of spaces.
EMPLOYMENT_TYPES = {"internship": "Internship", "full-time": "Full-time", "part-time": "Part-time"}
WORK_MODES = {"on-site": "On-site", "hybrid": "Hybrid", "remote": "Remote"}
CATEGORIES = [
    "Software Development", "Data Analytics", "Marketing", "Business", "Design", "Finance",
    "Human Resources", "Customer Support", "Engineering", "Project Management", "Sales", "Research",
]
CATEGORY_BY_LOWERCASE = {category.lower(): category for category in CATEGORIES}

REQUIRED_JOB_TEXT = ["title", "category", "employer", "location_name", "target_audience"]


# ---------- small helpers ----------


def clean_text(value) -> str:
    """Remove spaces at both ends and squeeze repeated spaces: '  Junior   Dev ' -> 'Junior Dev'."""
    return " ".join(str(value or "").split())


def split_list(value) -> list[str]:
    """'Python , python,, SQL' -> ['Python', 'SQL'] (trimmed, no empty items, no duplicates)."""
    items, seen = [], set()
    for item in str(value or "").split(","):
        item = clean_text(item)
        if item and item.lower() not in seen:
            seen.add(item.lower())
            items.append(item)
    return items


def lookup_key(value) -> str:
    """'FULL TIME' -> 'full-time', so different spellings find the same dictionary key."""
    return clean_text(value).lower().replace(" ", "-")


def parse_coordinate(value, name: str, limit: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} is not a number")
    if not -limit <= number <= limit:
        raise ValueError(f"{name} is out of range")
    return number


def parse_optional_int(value) -> int | None:
    """Whole number that is allowed to be missing. Empty, invalid or negative values become None."""
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def parse_int(value, name: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        raise ValueError(f"{name} is not a number")


# ---------- jobs ----------


def clean_job(row: dict) -> dict:
    """Return the cleaned job with real Python types.

    Raises ValueError with a short reason when the row cannot be repaired.
    """
    job = {"job_id": parse_int(row.get("job_id"), "job_id")}

    for field in REQUIRED_JOB_TEXT:
        job[field] = clean_text(row.get(field))
        if not job[field]:
            raise ValueError(f"missing {field}")

    job["description"] = clean_text(row.get("description")) or "No description provided."

    # Use the standard spelling of the category if we know it.
    job["category"] = CATEGORY_BY_LOWERCASE.get(job["category"].lower(), job["category"])

    job["employment_type"] = EMPLOYMENT_TYPES.get(lookup_key(row.get("employment_type")))
    if job["employment_type"] is None:
        raise ValueError("unknown employment_type")

    job["work_mode"] = WORK_MODES.get(lookup_key(row.get("work_mode")))
    if job["work_mode"] is None:
        raise ValueError("unknown work_mode")

    job["latitude"] = parse_coordinate(row.get("latitude"), "latitude", 90)
    job["longitude"] = parse_coordinate(row.get("longitude"), "longitude", 180)

    job["required_skills"] = split_list(row.get("required_skills"))
    if not job["required_skills"]:
        raise ValueError("no required_skills")

    salary_min = parse_optional_int(row.get("salary_min"))
    salary_max = parse_optional_int(row.get("salary_max"))
    if salary_min is not None and salary_max is not None and salary_min > salary_max:
        salary_min, salary_max = salary_max, salary_min
    job["salary_min"] = salary_min
    job["salary_max"] = salary_max

    try:
        job["application_deadline"] = date.fromisoformat(clean_text(row.get("application_deadline")))
    except ValueError:
        raise ValueError("invalid application_deadline")

    job["vacancies"] = parse_int(row.get("vacancies"), "vacancies")
    if job["vacancies"] < 1:
        raise ValueError("vacancies must be at least 1")

    filled = parse_optional_int(row.get("filled_positions")) or 0  # empty or invalid -> 0
    job["filled_positions"] = min(filled, job["vacancies"])

    return job


def clean_jobs(raw_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Clean every row. Returns (clean jobs, rejected rows with a 'reason' column)."""
    clean, rejected = [], []
    seen = {}  # duplicate key -> job_id of the first row with that key

    for row in raw_rows:
        try:
            job = clean_job(row)
        except ValueError as error:
            rejected.append({**row, "reason": str(error)})
            continue

        key = (job["title"].lower(), job["employer"].lower(),
               job["location_name"].lower(), job["employment_type"])
        if key in seen:
            rejected.append({**row, "reason": f"duplicate of job_id {seen[key]}"})
            continue
        seen[key] = job["job_id"]
        clean.append(job)

    return clean, rejected


# ---------- candidates ----------


def clean_candidate(row: dict) -> dict:
    """Return the cleaned candidate with real Python types (ValueError if it is not usable)."""
    candidate = {"candidate_id": parse_int(row.get("candidate_id"), "candidate_id")}

    for field in ["name", "email", "study_area"]:
        candidate[field] = clean_text(row.get(field))
        if not candidate[field]:
            raise ValueError(f"missing {field}")
    candidate["email"] = candidate["email"].lower()
    if "@" not in candidate["email"]:
        raise ValueError("invalid email")

    candidate["year_of_study"] = parse_int(row.get("year_of_study"), "year_of_study")
    if not 1 <= candidate["year_of_study"] <= 5:
        raise ValueError("year_of_study must be between 1 and 5")

    candidate["latitude"] = parse_coordinate(row.get("latitude"), "latitude", 90)
    candidate["longitude"] = parse_coordinate(row.get("longitude"), "longitude", 180)

    candidate["skills"] = split_list(row.get("skills"))
    if not candidate["skills"]:
        raise ValueError("no skills")
    candidate["interests"] = split_list(row.get("interests"))

    candidate["preferred_employment_type"] = EMPLOYMENT_TYPES.get(
        lookup_key(row.get("preferred_employment_type"))
    )
    candidate["preferred_work_mode"] = WORK_MODES.get(lookup_key(row.get("preferred_work_mode")))
    if candidate["preferred_employment_type"] is None or candidate["preferred_work_mode"] is None:
        raise ValueError("unknown employment type or work mode preference")

    try:
        candidate["available_from"] = time.fromisoformat(clean_text(row.get("available_from")))
        candidate["available_to"] = time.fromisoformat(clean_text(row.get("available_to")))
    except ValueError:
        raise ValueError("invalid availability time")
    if candidate["available_from"] >= candidate["available_to"]:
        raise ValueError("available_from must be earlier than available_to")

    candidate["min_salary"] = parse_optional_int(row.get("min_salary")) or 0
    return candidate


def clean_candidates(raw_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    clean, rejected = [], []
    seen_emails = set()

    for row in raw_rows:
        try:
            candidate = clean_candidate(row)
        except ValueError as error:
            rejected.append({**row, "reason": str(error)})
            continue
        if candidate["email"] in seen_emails:
            rejected.append({**row, "reason": "duplicate email"})
            continue
        seen_emails.add(candidate["email"])
        clean.append(candidate)

    return clean, rejected


# ---------- files ----------


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as file:
        if not rows:
            return  # nothing to write, leave an empty file
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            # Lists go back to "a,b,c" text and None becomes an empty cell.
            writer.writerow({
                key: ",".join(value) if isinstance(value, list) else ("" if value is None else value)
                for key, value in row.items()
            })


def load_clean_data() -> tuple[list[dict], list[dict]]:
    """Run the whole cleaning step. Returns (clean jobs, clean candidates)."""
    jobs, rejected_jobs = clean_jobs(read_csv(RAW_JOBS_FILE))
    candidates, rejected_candidates = clean_candidates(read_csv(CANDIDATES_FILE))

    write_csv(CLEAN_JOBS_FILE, jobs)
    write_csv(REJECTED_JOBS_FILE, rejected_jobs)

    print(f"Jobs:       {len(jobs)} clean, {len(rejected_jobs)} rejected")
    for row in rejected_jobs:
        print(f"  - job_id {row['job_id']}: {row['reason']}")
    print(f"Candidates: {len(candidates)} clean, {len(rejected_candidates)} rejected")
    for row in rejected_candidates:
        print(f"  - candidate_id {row['candidate_id']}: {row['reason']}")

    return jobs, candidates


if __name__ == "__main__":
    load_clean_data()
