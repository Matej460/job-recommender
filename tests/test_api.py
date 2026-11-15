"""Tests for the API endpoints (they use the `client` fixture from conftest.py).

Run:  uv run pytest
"""

from datetime import date, timedelta


def job_payload(**changes) -> dict:
    """A valid body for POST /jobs. Tests change only the fields they need."""
    payload = {
        "title": "Python Developer Intern",
        "description": "Build backend APIs",
        "category": "Software Development",
        "employer": "TechNova",
        "location_name": "Skopje - Centar",
        "latitude": 41.9981,
        "longitude": 21.4254,
        "employment_type": "Internship",
        "work_mode": "Hybrid",
        "required_skills": ["Python", "SQL", "Git"],
        "target_audience": "Computer Science",
        "salary_min": 25000,
        "salary_max": 30000,
        "application_deadline": (date.today() + timedelta(days=30)).isoformat(),
        "vacancies": 3,
        "filled_positions": 1,
    }
    payload.update(changes)
    return payload


def candidate_payload(**changes) -> dict:
    """A valid body for POST /candidates."""
    payload = {
        "name": "Ana Petrova",
        "email": "ana.pet@example.com",
        "study_area": "Computer Science",
        "year_of_study": 3,
        "latitude": 41.9980,
        "longitude": 21.4250,
        "skills": ["Python", "SQL", "Git"],
        "interests": ["Software Development", "Data Analytics"],
        "preferred_employment_type": "Internship",
        "preferred_work_mode": "Hybrid",
        "available_from": "09:00",
        "available_to": "17:00",
        "min_salary": 20000,
    }
    payload.update(changes)
    return payload


# ---------- Jobs ----------


def test_create_job_and_read_it_back(client):
    created = client.post("/jobs", json=job_payload())
    assert created.status_code == 201
    job = created.json()
    assert job["id"] == 1
    assert job["available_positions"] == 2  # 3 vacancies - 1 filled

    fetched = client.get("/jobs/1")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Python Developer Intern"


def test_unknown_job_returns_404(client):
    assert client.get("/jobs/999").status_code == 404


def test_invalid_job_is_rejected(client):
    assert client.post("/jobs", json=job_payload(employment_type="Volunteer")).status_code == 422
    assert client.post("/jobs", json=job_payload(salary_min=50000, salary_max=10000)).status_code == 422
    assert client.post("/jobs", json=job_payload(required_skills=[])).status_code == 422
    assert client.post("/jobs", json=job_payload(vacancies=2, filled_positions=5)).status_code == 422


def test_job_filters_work_alone_and_together(client):
    client.post("/jobs", json=job_payload(title="Job A", category="Software Development",
                                          employment_type="Internship", work_mode="Remote"))
    client.post("/jobs", json=job_payload(title="Job B", category="Software Development",
                                          employment_type="Full-time", work_mode="On-site"))
    client.post("/jobs", json=job_payload(title="Job C", category="Marketing",
                                          employment_type="Internship", work_mode="Remote"))
    client.post("/jobs", json=job_payload(title="Job D", category="Marketing",
                                          employment_type="Part-time", work_mode="Hybrid"))

    def titles(query: str) -> list[str]:
        return [job["title"] for job in client.get("/jobs" + query).json()]

    assert titles("") == ["Job A", "Job B", "Job C", "Job D"]
    assert titles("?category=Software Development") == ["Job A", "Job B"]
    assert titles("?category=software development") == ["Job A", "Job B"]  # not case-sensitive
    assert titles("?employment_type=Internship") == ["Job A", "Job C"]
    assert titles("?remote_only=true") == ["Job A", "Job C"]
    assert titles("?category=Software Development&employment_type=Internship&remote_only=true") == ["Job A"]
    assert titles("?category=Marketing&employment_type=Full-time") == []


def test_soft_deleted_job_disappears_from_the_api(client):
    client.post("/jobs", json=job_payload())
    assert client.delete("/jobs/1").status_code == 204
    assert client.get("/jobs/1").status_code == 404
    assert client.get("/jobs").json() == []


# ---------- Candidates ----------


def test_create_list_and_get_candidate(client):
    created = client.post("/candidates", json=candidate_payload())
    assert created.status_code == 201
    assert created.json()["skills"] == ["Python", "SQL", "Git"]

    assert len(client.get("/candidates").json()) == 1
    assert client.get("/candidates/1").json()["name"] == "Ana Petrova"
    assert client.get("/candidates/999").status_code == 404


def test_candidate_validation(client):
    client.post("/candidates", json=candidate_payload())
    # the same e-mail twice
    assert client.post("/candidates", json=candidate_payload()).status_code == 409
    # not an e-mail address
    assert client.post("/candidates", json=candidate_payload(email="not-an-email")).status_code == 422
    # availability ends before it starts
    wrong_hours = candidate_payload(email="b@example.com", available_from="18:00", available_to="09:00")
    assert client.post("/candidates", json=wrong_hours).status_code == 422


def test_soft_deleted_candidate_disappears_from_the_api(client):
    client.post("/candidates", json=candidate_payload())
    assert client.delete("/candidates/1").status_code == 204
    assert client.get("/candidates/1").status_code == 404
    assert client.get("/recommendations/1").status_code == 404


# ---------- Recommendations ----------


def create_sample_data(client) -> None:
    """One candidate and five jobs: perfect match, weak match, far away, expired, filled."""
    client.post("/candidates", json=candidate_payload())
    client.post("/jobs", json=job_payload(title="Perfect match"))
    client.post("/jobs", json=job_payload(title="Weak match", category="Sales",
                                          required_skills=["Negotiation", "CRM"],
                                          target_audience="Economics", employment_type="Full-time"))
    client.post("/jobs", json=job_payload(title="Far away", work_mode="On-site",
                                          latitude=41.0297, longitude=21.3292))
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    client.post("/jobs", json=job_payload(title="Expired", application_deadline=yesterday))
    client.post("/jobs", json=job_payload(title="Filled", vacancies=2, filled_positions=2))


def test_recommendations_for_candidate(client):
    create_sample_data(client)
    response = client.get("/recommendations/1")
    assert response.status_code == 200
    body = response.json()

    assert body["candidate_id"] == 1
    assert body["candidate_name"] == "Ana Petrova"

    titles = [item["title"] for item in body["recommendations"]]
    assert titles == ["Perfect match", "Far away", "Weak match"]  # expired and filled are left out

    scores = [item["score"] for item in body["recommendations"]]
    assert scores == sorted(scores, reverse=True)

    # every field from the example response in the project brief is present
    expected_fields = {
        "job_id", "title", "category", "employer", "employment_type", "work_mode",
        "location_name", "distance_km", "salary_min", "salary_max", "application_deadline",
        "available_positions", "score", "reason",
    }
    assert expected_fields <= set(body["recommendations"][0])


def test_recommendations_for_unknown_candidate_returns_404(client):
    assert client.get("/recommendations/999").status_code == 404


def test_recommendations_accept_the_job_filters_and_limit(client):
    create_sample_data(client)
    sales = client.get("/recommendations/1?category=Sales").json()["recommendations"]
    assert [item["title"] for item in sales] == ["Weak match"]

    nothing = client.get("/recommendations/1?remote_only=true").json()["recommendations"]
    assert nothing == []

    top_one = client.get("/recommendations/1?limit=1").json()["recommendations"]
    assert len(top_one) == 1


def test_recommendations_by_location_and_skills(client):
    create_sample_data(client)
    response = client.get("/recommendations?lat=41.9981&lon=21.4254&skills=Python,SQL,Git")
    assert response.status_code == 200
    body = response.json()

    assert body["candidate_id"] is None
    best = body["recommendations"][0]
    assert best["title"] == "Perfect match"
    # only the criteria that can be checked without a saved profile are used
    assert [row["criterion"] for row in best["score_breakdown"]] == ["skills", "distance", "availability"]


def test_recommendations_by_location_need_all_three_parameters(client):
    assert client.get("/recommendations?lat=41.99&lon=21.42").status_code == 422
    assert client.get("/recommendations?lat=500&lon=21.42&skills=Python").status_code == 422
    assert client.get("/recommendations?lat=41.99&lon=21.42&skills=,").status_code == 422


# ---------- Applications (optional extension) ----------


def test_applying_removes_the_job_from_recommendations(client):
    create_sample_data(client)

    applied = client.post("/applications", json={"candidate_id": 1, "job_id": 1})
    assert applied.status_code == 201
    assert applied.json()["status"] == "submitted"

    # applying twice is not allowed
    assert client.post("/applications", json={"candidate_id": 1, "job_id": 1}).status_code == 409
    # the expired job (id 4) does not accept applications
    assert client.post("/applications", json={"candidate_id": 1, "job_id": 4}).status_code == 400

    assert len(client.get("/candidates/1/applications").json()) == 1
    titles = [item["title"] for item in client.get("/recommendations/1").json()["recommendations"]]
    assert "Perfect match" not in titles
