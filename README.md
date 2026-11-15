# Job and Internship Recommendation System

Project for the subject **Implementation of Solution 2**.

**GitHub repository:** https://github.com/Matej460/job-recommender

**Technical documentation (PDF):** [docs/Technical_Documentation.pdf](docs/Technical_Documentation.pdf)

A small web application that recommends jobs and internships to students and recent
graduates. The ranking is **deterministic and rule-based**: no machine learning, every
point of the score can be explained.

- **Backend:** Python, FastAPI, SQLAlchemy, psycopg2
- **Database:** PostgreSQL 16 (Docker)
- **Frontend:** HTML, CSS, JavaScript (no framework)
- **Tools:** uv, python-dotenv, pytest

## Contents

1. [How it works](#1-how-it-works)
2. [Project structure](#2-project-structure)
3. [How to run](#3-how-to-run)
4. [Data preparation](#4-data-preparation)
5. [Database](#5-database)
6. [API](#6-api)
7. [Recommendation logic](#7-recommendation-logic)
8. [Frontend](#8-frontend)
9. [Testing](#9-testing)
10. [Optional extensions](#10-optional-extensions)

## 1. How it works

```
data/raw/jobs.csv ─┐
data/candidates.csv ┴─> clean_data.py ──> seed_db.py ──> PostgreSQL
                         (validate)        (insert)          │
                                                             ▼
frontend (HTML/CSS/JS) ──HTTP/JSON──> FastAPI routers ──> crud.py (queries)
                                            │
                                            └──> scoring.py (rules, no database)
```

1. `generate_data.py` creates the synthetic CSV files.
2. `seed_db.py` cleans and validates them and inserts the rows into PostgreSQL.
3. The frontend asks the API for recommendations for one candidate.
4. The API reads the candidate and the active jobs from the database, `scoring.py`
   removes closed jobs, scores the rest and sorts them from the highest score to the lowest.
5. The frontend shows the result as cards.

## 2. Project structure

```
app/
  main.py              FastAPI app, CORS, routers, serves the frontend
  config.py            settings from .env
  database.py          engine, session, get_db dependency
  models.py            tables: candidates, jobs, job_applications
  schemas.py           Pydantic schemas (validation of input and output)
  crud.py              all database queries
  scoring.py           recommendation rules (pure functions)
  routers/
    jobs.py            /jobs
    candidates.py      /candidates
    recommendations.py /recommendations
    applications.py    /applications (optional extension)
scripts/
  generate_data.py     creates the CSV datasets
  clean_data.py        cleans and validates the CSV datasets
  seed_db.py           fills PostgreSQL
  smoke_test.py        checks every endpoint on the running server
data/
  raw/jobs.csv                   159 raw rows (150 valid + 9 broken on purpose)
  candidates.csv                 80 candidates
  processed/jobs_clean.csv       150 rows that were inserted
  processed/jobs_rejected.csv    9 rejected rows with the reason
frontend/
  index.html, style.css, app.js
tests/
  test_scoring.py      unit tests of the scoring rules
  test_api.py          tests of the endpoints
docs/
  TESTING.md           test results and screenshots
docker-compose.yml     PostgreSQL container
pyproject.toml         dependencies (uv)
```

## 3. How to run

Requirements: [uv](https://docs.astral.sh/uv/) and Docker Desktop (running).

```bash
# 0. Clone the repository
git clone https://github.com/Matej460/job-recommender.git
cd job-recommender

# 1. Install the dependencies into .venv
uv sync

# 2. Start PostgreSQL
docker compose up -d

# 3. Create the datasets and fill the database
uv run python -m scripts.generate_data
uv run python -m scripts.seed_db

# 4. Start the API
uv run uvicorn app.main:app --reload
```

Then open:

- Frontend: <http://127.0.0.1:8000/frontend/index.html?candidate_id=1>
- API documentation (Swagger): <http://127.0.0.1:8000/docs>

The frontend also works when `frontend/index.html` is opened directly from disk or with
VS Code Live Server, as long as the API runs on port 8000.

**Settings.** The application works without any configuration. To change the database
user, password or port, copy `.env.example` to `.env` and edit it. The same file is used
by `docker-compose.yml` and by the application.

**Fresh deadlines.** Application deadlines are calculated from the date on which
`generate_data` is run. Run step 3 again on the day of a demo, so the dataset has
open jobs. The generator uses a fixed random seed, so the jobs and candidates stay the same.

**Problems.**

| Problem | Solution |
|---|---|
| `port is already allocated` on `docker compose up` | Another PostgreSQL uses port 5432. Put `POSTGRES_PORT=5433` in `.env` and run `docker compose up -d` again. |
| `connection refused` when seeding or starting the API | The container is not running. Check with `docker compose ps`. |
| The frontend shows "Cannot reach the API" | Start the API (step 4). |
| Start again from an empty database | `docker compose down -v`, then steps 2 and 3. |

## 4. Data preparation

Both datasets are synthetic and all employers and people are fictional.

| File | Rows | Content |
|---|---|---|
| `data/raw/jobs.csv` | 159 | 12 categories, 32 employers, 11 locations (Skopje districts and other cities) |
| `data/candidates.csv` | 80 | 10 study areas, several skills and interests per candidate |

`skills`, `interests` and `required_skills` hold several values, written in the CSV as
`"Python,SQL,Git"`.

The raw jobs file is messy on purpose, so the cleaning step has real work to do.
`scripts/clean_data.py` handles every row like this:

| Fixed automatically | Rejected (row is not inserted) |
|---|---|
| extra spaces in text | a required text field is empty |
| different spelling of employment type, work mode, category (`FULL TIME` → `Full-time`) | unknown employment type or work mode |
| skill lists: trimmed, empty items and duplicates removed | no required skills |
| `salary_min` > `salary_max` → swapped | latitude or longitude missing, not a number or out of range |
| invalid or negative salary → treated as "not advertised" | invalid deadline date |
| `filled_positions` > `vacancies` → limited to `vacancies` | `vacancies` below 1 |
| | duplicate of an earlier row (same title, employer, location, employment type) |

Result: 150 clean rows in `data/processed/jobs_clean.csv` and 9 rejected rows with the
reason in `data/processed/jobs_rejected.csv`.

The salaries are monthly amounts in MKD for every job and every candidate.

## 5. Database

Three tables. Every table has `created_at`, `updated_at` and `deleted_at`
(defined once in `TimestampMixin` in `app/models.py`).

**candidates**: `id`, `name`, `email` (unique), `study_area`, `year_of_study`
(1 to 4 = student, 5 = recent graduate), `latitude`, `longitude`, `skills` (JSON list),
`interests` (JSON list), `preferred_employment_type`, `preferred_work_mode`,
`available_from`, `available_to`, `min_salary`

**jobs**: `id`, `title`, `description`, `category`, `employer`, `location_name`,
`latitude`, `longitude`, `employment_type`, `work_mode`, `required_skills` (JSON list),
`target_audience`, `salary_min`, `salary_max` (both can be NULL), `application_deadline`,
`vacancies`, `filled_positions`

**job_applications** (optional): `id`, `candidate_id` → candidates, `job_id` → jobs,
`application_datetime`, `status`

Design decisions:

- **Lists as JSON columns.** Skills and interests are stored as JSON lists, so SQLAlchemy
  returns them as Python lists and no extra tables are needed.
- **Soft delete.** `deleted_at` is NULL for active rows. Deleting sets a timestamp and
  every query filters on `deleted_at IS NULL`, so the row is hidden but not lost.
- **Timestamps are set by the database** (`server_default=now()`, `onupdate=now()`).
- `available_positions` is not stored. It is calculated as `vacancies - filled_positions`.

## 6. API

| Method | Path | Description |
|---|---|---|
| GET | `/jobs` | Active jobs. Filters: `category`, `employment_type`, `remote_only` |
| GET | `/jobs/{job_id}` | One job |
| POST | `/jobs` | Create a job |
| GET | `/candidates` | All candidates |
| GET | `/candidates/{candidate_id}` | One candidate |
| POST | `/candidates` | Create a candidate (unique e-mail) |
| GET | `/recommendations/{candidate_id}` | Ranked jobs for a saved candidate |
| GET | `/recommendations?lat=..&lon=..&skills=..` | Ranked jobs for a visitor with only location and skills |

Both recommendation endpoints also accept the three job filters and `limit` (default 20).

Filter examples:

```text
GET /jobs?category=Software Development
GET /jobs?employment_type=Internship
GET /jobs?remote_only=true
GET /jobs?category=Software Development&employment_type=Internship&remote_only=true
```

The filters are combined with AND and are not case-sensitive.

Status codes: `200` OK, `201` created, `404` not found, `409` e-mail already exists,
`422` invalid input.

Example: `GET /recommendations/1?limit=1`

```json
{
  "candidate_id": 1,
  "candidate_name": "Ana Petrova",
  "recommendations": [
    {
      "job_id": 69,
      "title": "Part-time Data Analyst",
      "category": "Data Analytics",
      "employer": "Balkan Analytics",
      "employment_type": "Part-time",
      "work_mode": "On-site",
      "location_name": "Skopje - Cair",
      "distance_km": 1.74,
      "salary_min": 28000,
      "salary_max": 35000,
      "application_deadline": "2026-11-27",
      "available_positions": 5,
      "score": 91.5,
      "reason": "Matches your Python and SQL skills, fits your interest in Data Analytics, is close to your location and meets your salary expectation.",
      "score_breakdown": [
        {"criterion": "skills", "points": 30.0, "max_points": 30},
        {"criterion": "interests", "points": 10.0, "max_points": 10}
      ]
    }
  ]
}
```

(`score_breakdown` has one row per criterion; it is shortened here.)

## 7. Recommendation logic

All rules are in `app/scoring.py`. The constants at the top of that file are the only
place where weights and thresholds are defined.

### Step 1: eligibility

A job is never recommended when:

- it is soft-deleted (`deleted_at` is set),
- the application deadline has passed (a deadline of today is still open),
- no position is left (`vacancies - filled_positions` is 0),
- the candidate already applied for it.

### Step 2: score (0 to 100)

Each criterion gives a fraction from 0 to 1. The fraction is multiplied by the weight of
the criterion and the points are added together.

| Group from the brief | Criterion | Max points | Rule |
|---|---|---:|---|
| Skills and interests | `skills` | 30 | matched required skills ÷ all required skills (2 of 3 → 20 points) |
| | `interests` | 10 | job category is one of the candidate's interests |
| Education / audience | `audience` | 10 | targets the candidate's study area → 100%; open to all (`All Graduates`) → 70%; other study area → 0 |
| | `year_of_study` | 5 | Internship and part-time: every year → 100%. Full-time: year 4 or graduate → 100%, year 3 → 50%, years 1 and 2 → 0 |
| Employment type and schedule | `employment_type` | 10 | same as preferred → 100%; Internship ↔ Part-time → 50%; otherwise 0 |
| | `schedule` | 5 | share of the expected working hours in which the candidate is available |
| Distance / work mode | `work_mode` | 5 | same as preferred → 100%; one step away (Hybrid ↔ On-site, Hybrid ↔ Remote) → 50%; On-site ↔ Remote → 0 |
| | `distance` | 10 | Remote → 100%. Otherwise `1 - distance / max`, where max is 30 km for on-site and 60 km for hybrid |
| Salary | `salary` | 10 | lowest offer ≥ expected → 100%; expected is inside the range → 70%; highest offer < expected → 0; salary not advertised → 50% |
| Vacancies / deadline | `availability` | 5 | average of (open positions ÷ vacancies) and (days left ÷ 7, at most 1) |
| | **Total** | **100** | |

Expected working hours per employment type (the dataset has no schedule field):
Full-time 09:00 to 17:00, Internship 09:00 to 15:00, Part-time 09:00 to 13:00.

The distance is calculated with the Haversine formula from the coordinates of the
candidate and of the workplace.

### Why these weights

- **Skills (30)** have the highest weight, because they show whether the candidate can do
  the job at all. Together with interests the group has 40 of 100 points.
- **What the candidate wants** comes next: interests (10) and employment type (10).
- **Education (15)**: a job aimed at the candidate's study area is a better fit than one
  open to everyone, and a full-time job is not realistic for a first- or second-year student.
- **Practical fit (20)**: distance (10), work mode (5) and schedule (5). A hybrid job needs
  fewer trips, so the acceptable distance is twice as long.
- **Salary (10)** matters, but an internship with a lower salary can still be valuable,
  so it does not dominate.
- **Availability (5)** is small, because closed jobs are already removed in step 1. It only
  prefers jobs with more free positions and enough time to apply.

### Step 3: ranking

Jobs are sorted by score from the highest to the lowest. Equal scores are ordered by the
earlier deadline and then by job id, so the same input always gives exactly the same list.
The first `limit` jobs are returned (default 20).

### Special cases

| Case | Handling |
|---|---|
| Expired listing | Removed before scoring |
| All vacancies filled | Removed before scoring |
| Salary not advertised | Job stays, salary criterion gives 50% (neither rewarded nor punished) |
| Only one salary value given | It is used as both ends of the range |
| Remote job | No distance is calculated (`distance_km` is `null`), distance criterion gives 100% |
| No matching skills | Job stays with 0 of 30 skill points, so it can still appear because of the other criteria. The reason text says that no required skill matches |
| Job for another study area | Job stays, audience criterion gives 0 |
| Visitor without a profile (`?lat&lon&skills`) | Criteria that need unknown information are skipped. The score is `100 × earned ÷ possible` over the checked criteria (skills, distance, availability) |

### Worked example

Candidate 1 (Ana Petrova: Computer Science, year 3, skills Python/SQL/Git, wants an
Internship, Hybrid, available 09:00 to 17:00, at least 20,000 MKD) and job 1
(Junior Python Developer: Full-time, Hybrid, requires Python/SQL/Git, Computer Science,
45,000 to 65,000 MKD, 2 of 3 positions open, deadline in 45 days, 0.03 km away):

| Criterion | Calculation | Points |
|---|---|---:|
| skills | 3 of 3 → 1.0 × 30 | 30.0 |
| interests | Software Development is an interest → 1.0 × 10 | 10.0 |
| audience | Computer Science = Computer Science → 1.0 × 10 | 10.0 |
| year_of_study | full-time job, year 3 → 0.5 × 5 | 2.5 |
| employment_type | wants Internship, job is Full-time → 0 × 10 | 0.0 |
| schedule | 09:00 to 17:00 fully covered → 1.0 × 5 | 5.0 |
| work_mode | Hybrid = Hybrid → 1.0 × 5 | 5.0 |
| distance | 1 - 0.03 / 60 → 1.0 × 10 | 10.0 |
| salary | 45,000 ≥ 20,000 → 1.0 × 10 | 10.0 |
| availability | (2/3 + 1) / 2 = 0.83 × 5 | 4.2 |
| **Score** | | **86.7** |

The same breakdown is returned by the API in `score_breakdown` and shown on every card
in the frontend ("How this score was calculated").

## 8. Frontend

One page (`frontend/index.html`) with plain JavaScript:

- candidate selector, and support for `index.html?candidate_id=1`
- two views: **Recommended** (`GET /recommendations/{id}`) and **All jobs** (`GET /jobs`)
- the three filters (category, employment type, remote only) work in both views and are
  sent to the API as query parameters
- each recommendation card shows title, employer, category, employment type, work mode,
  location with distance or remote status, salary range, deadline, open positions, score,
  the reason, and the score breakdown
- loading, error (with "Try again") and empty states
- responsive layout: one column, the controls stack on small screens

## 9. Testing

```bash
uv run pytest                          # 42 automated tests, no database or server needed
uv run python -m scripts.smoke_test    # checks every endpoint on the running server
```

- `tests/test_scoring.py`: every scoring rule, eligibility, special cases, ranking.
- `tests/test_api.py`: every endpoint, the filters, validation and error codes. These tests
  use a temporary in-memory SQLite database, so the PostgreSQL data is never changed.
- `scripts/smoke_test.py`: real requests against the running API with PostgreSQL.

Results and screenshots of the frontend are in [docs/TESTING.md](docs/TESTING.md).

## 10. Optional extensions

- **Job applications:** `POST /applications`, `GET /candidates/{id}/applications`. Jobs a
  candidate already applied for are not recommended to that candidate again.
- **Soft delete:** `DELETE /jobs/{id}` and `DELETE /candidates/{id}` set `deleted_at`.
- **Score breakdown** in the API response and in the frontend.
- **Filters on recommendations**, not only on `/jobs`.
