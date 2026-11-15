"""Quick check of every required endpoint against the RUNNING server (real PostgreSQL data).

1. Start the server:  uv run uvicorn app.main:app
2. In a second terminal:  uv run python -m scripts.smoke_test

The script creates one test job and one test candidate and removes them again
(soft delete), so the demo data stays clean.
"""

import os
import sys
import time
from datetime import date, timedelta

import requests

# Override with e.g.  API_URL=http://127.0.0.1:8001
BASE_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
failed = 0


def check(name: str, condition: bool, details: str = "") -> None:
    """Print one line per check and count the failures."""
    global failed
    if not condition:
        failed += 1
    print(f"[{'PASS' if condition else 'FAIL'}] {name}" + (f"  ({details})" if details else ""))


def get(path: str, **params) -> requests.Response:
    return requests.get(BASE_URL + path, params=params, timeout=10)


def main() -> None:
    # ----- GET /jobs and its three filters -----
    jobs = get("/jobs").json()
    check("GET /jobs", len(jobs) > 0, f"{len(jobs)} jobs")

    by_category = get("/jobs", category="Software Development").json()
    check("GET /jobs?category=Software Development",
          len(by_category) > 0 and all(job["category"] == "Software Development" for job in by_category),
          f"{len(by_category)} jobs")

    internships = get("/jobs", employment_type="Internship").json()
    check("GET /jobs?employment_type=Internship",
          len(internships) > 0 and all(job["employment_type"] == "Internship" for job in internships),
          f"{len(internships)} jobs")

    remote = get("/jobs", remote_only="true").json()
    check("GET /jobs?remote_only=true",
          len(remote) > 0 and all(job["work_mode"] == "Remote" for job in remote),
          f"{len(remote)} jobs")

    combined = get("/jobs", category="Software Development", employment_type="Internship",
                   remote_only="true").json()
    check("GET /jobs with all three filters",
          all(job["category"] == "Software Development" and job["employment_type"] == "Internship"
              and job["work_mode"] == "Remote" for job in combined),
          f"{len(combined)} jobs")

    # ----- GET /jobs/{job_id} -----
    check("GET /jobs/1", get("/jobs/1").status_code == 200)
    check("GET /jobs/999999 returns 404", get("/jobs/999999").status_code == 404)

    # ----- candidates -----
    candidates = get("/candidates").json()
    check("GET /candidates", len(candidates) > 0, f"{len(candidates)} candidates")
    check("GET /candidates/1", get("/candidates/1").status_code == 200)
    check("GET /candidates/999999 returns 404", get("/candidates/999999").status_code == 404)

    # ----- GET /recommendations/{candidate_id} -----
    response = get("/recommendations/1")
    items = response.json()["recommendations"]
    scores = [item["score"] for item in items]
    today = date.today().isoformat()
    check("GET /recommendations/1", response.status_code == 200 and len(items) > 0,
          f"{len(items)} recommendations, best score {scores[0] if scores else '-'}")
    check("  sorted from highest to lowest score", scores == sorted(scores, reverse=True))
    check("  no expired or filled jobs",
          all(item["application_deadline"] >= today and item["available_positions"] > 0 for item in items))
    check("GET /recommendations/999999 returns 404", get("/recommendations/999999").status_code == 404)

    # ----- GET /recommendations?lat=..&lon=..&skills=.. -----
    response = get("/recommendations", lat=41.9981, lon=21.4254, skills="Python,SQL,Git")
    check("GET /recommendations?lat=...&lon=...&skills=...",
          response.status_code == 200 and len(response.json()["recommendations"]) > 0)

    # ----- POST /jobs (and remove the test job again) -----
    new_job = {
        "title": "Smoke Test Job", "description": "Created by scripts/smoke_test.py",
        "category": "Research", "employer": "Test Employer", "location_name": "Skopje - Centar",
        "latitude": 41.9961, "longitude": 21.4317, "employment_type": "Part-time",
        "work_mode": "Remote", "required_skills": ["Excel"], "target_audience": "All Graduates",
        "salary_min": 18000, "salary_max": 24000,
        "application_deadline": (date.today() + timedelta(days=14)).isoformat(),
        "vacancies": 1, "filled_positions": 0,
    }
    response = requests.post(BASE_URL + "/jobs", json=new_job, timeout=10)
    check("POST /jobs", response.status_code == 201, f"status {response.status_code}")
    if response.status_code == 201:
        requests.delete(f"{BASE_URL}/jobs/{response.json()['id']}", timeout=10)

    invalid_job = {**new_job, "employment_type": "Volunteer"}
    response = requests.post(BASE_URL + "/jobs", json=invalid_job, timeout=10)
    check("POST /jobs with invalid data returns 422", response.status_code == 422)

    # ----- POST /candidates (and remove the test candidate again) -----
    new_candidate = {
        "name": "Smoke Test", "email": f"smoke.test.{int(time.time())}@example.com",
        "study_area": "Computer Science", "year_of_study": 2, "latitude": 41.9961,
        "longitude": 21.4317, "skills": ["Python"], "interests": ["Research"],
        "preferred_employment_type": "Part-time", "preferred_work_mode": "Remote",
        "available_from": "09:00", "available_to": "13:00", "min_salary": 15000,
    }
    response = requests.post(BASE_URL + "/candidates", json=new_candidate, timeout=10)
    check("POST /candidates", response.status_code == 201, f"status {response.status_code}")
    if response.status_code == 201:
        requests.delete(f"{BASE_URL}/candidates/{response.json()['id']}", timeout=10)

    print()
    print("All checks passed." if failed == 0 else f"{failed} check(s) failed.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    try:
        main()
    except requests.ConnectionError:
        print(f"Cannot reach the API at {BASE_URL}. Start it with: uv run uvicorn app.main:app")
        sys.exit(1)
