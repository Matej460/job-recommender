"""Unit tests for the scoring rules. They need no database and no running server.

Run:  uv run pytest
"""

from datetime import date, time, timedelta

import pytest

from app import scoring
from app.models import Candidate, Job

TODAY = date(2026, 11, 10)  # a fixed "today", so the tests give the same result on any day


def make_job(**changes) -> Job:
    """A job that fits the default candidate perfectly. Tests change only what they check."""
    values = dict(
        id=1, title="Python Developer Intern", description="Build APIs",
        category="Software Development", employer="TechNova", location_name="Skopje - Centar",
        latitude=41.9981, longitude=21.4254, employment_type="Internship", work_mode="Hybrid",
        required_skills=["Python", "SQL", "Git"], target_audience="Computer Science",
        salary_min=25000, salary_max=30000, application_deadline=TODAY + timedelta(days=30),
        vacancies=2, filled_positions=0,
    )
    values.update(changes)
    return Job(**values)


def make_candidate(**changes) -> Candidate:
    values = dict(
        id=1, name="Ana Petrova", email="ana.pet@example.com", study_area="Computer Science",
        year_of_study=3, latitude=41.9981, longitude=21.4254, skills=["Python", "SQL", "Git"],
        interests=["Software Development", "Data Analytics"],
        preferred_employment_type="Internship", preferred_work_mode="Hybrid",
        available_from=time(9, 0), available_to=time(17, 0), min_salary=20000,
    )
    values.update(changes)
    return Candidate(**values)


# ---------- Haversine ----------


def test_haversine_same_point_is_zero():
    assert scoring.haversine_km(41.9981, 21.4254, 41.9981, 21.4254) == 0


def test_haversine_skopje_to_bitola():
    # The real straight-line distance between the two cities is about 108 km.
    distance = scoring.haversine_km(41.9981, 21.4254, 41.0297, 21.3292)
    assert 105 < distance < 111


# ---------- Eligibility ----------


def test_open_job_is_eligible():
    assert scoring.is_eligible(make_job(), TODAY)


def test_deadline_today_is_still_eligible():
    assert scoring.is_eligible(make_job(application_deadline=TODAY), TODAY)


def test_expired_job_is_not_eligible():
    assert not scoring.is_eligible(make_job(application_deadline=TODAY - timedelta(days=1)), TODAY)


def test_filled_job_is_not_eligible():
    assert not scoring.is_eligible(make_job(vacancies=2, filled_positions=2), TODAY)


def test_soft_deleted_job_is_not_eligible():
    assert not scoring.is_eligible(make_job(deleted_at=TODAY), TODAY)


# ---------- The ten criteria ----------


def test_skills_fraction_counts_matching_skills():
    candidate = make_candidate(skills=["python", " SQL "])  # letter case and spaces do not matter
    assert scoring.skills_fraction(candidate, make_job()) == pytest.approx(2 / 3)
    assert scoring.skills_fraction(make_candidate(skills=["Figma"]), make_job()) == 0


def test_interests_fraction():
    assert scoring.interests_fraction(make_candidate(), make_job()) == 1.0
    assert scoring.interests_fraction(make_candidate(), make_job(category="Sales")) == 0.0


def test_audience_fraction():
    candidate = make_candidate()
    assert scoring.audience_fraction(candidate, make_job()) == 1.0
    assert scoring.audience_fraction(candidate, make_job(target_audience="All Graduates")) == 0.7
    assert scoring.audience_fraction(candidate, make_job(target_audience="Finance")) == 0.0


def test_year_of_study_fraction():
    full_time = make_job(employment_type="Full-time")
    assert scoring.year_of_study_fraction(make_candidate(year_of_study=1), make_job()) == 1.0
    assert scoring.year_of_study_fraction(make_candidate(year_of_study=2), full_time) == 0.0
    assert scoring.year_of_study_fraction(make_candidate(year_of_study=3), full_time) == 0.5
    assert scoring.year_of_study_fraction(make_candidate(year_of_study=5), full_time) == 1.0


def test_employment_type_fraction():
    candidate = make_candidate(preferred_employment_type="Internship")
    assert scoring.employment_type_fraction(candidate, make_job(employment_type="Internship")) == 1.0
    assert scoring.employment_type_fraction(candidate, make_job(employment_type="Part-time")) == 0.5
    assert scoring.employment_type_fraction(candidate, make_job(employment_type="Full-time")) == 0.0


def test_schedule_fraction_is_the_share_of_covered_working_hours():
    full_time = make_job(employment_type="Full-time")  # expected 09:00-17:00
    late = make_candidate(available_from=time(10, 0), available_to=time(18, 0))
    evening = make_candidate(available_from=time(17, 0), available_to=time(21, 0))
    assert scoring.schedule_fraction(late, full_time) == 7 / 8
    assert scoring.schedule_fraction(evening, full_time) == 0.0


def test_work_mode_fraction():
    candidate = make_candidate(preferred_work_mode="On-site")
    assert scoring.work_mode_fraction(candidate, make_job(work_mode="On-site")) == 1.0
    assert scoring.work_mode_fraction(candidate, make_job(work_mode="Hybrid")) == 0.5
    assert scoring.work_mode_fraction(candidate, make_job(work_mode="Remote")) == 0.0


def test_distance_fraction():
    on_site = make_job(work_mode="On-site")   # points reach zero at 30 km
    hybrid = make_job(work_mode="Hybrid")     # points reach zero at 60 km
    assert scoring.distance_fraction(on_site, 0) == 1.0
    assert scoring.distance_fraction(on_site, 15) == 0.5
    assert scoring.distance_fraction(on_site, 80) == 0.0
    assert scoring.distance_fraction(hybrid, 30) == 0.5


def test_remote_job_has_no_distance_and_full_distance_points():
    remote = make_job(work_mode="Remote", latitude=41.0297, longitude=21.3292)  # office in Bitola
    assert scoring.distance_km(make_candidate(), remote) is None
    assert scoring.distance_fraction(remote, None) == 1.0


def test_salary_fraction():
    candidate = make_candidate(min_salary=20000)
    assert scoring.salary_fraction(candidate, make_job(salary_min=20000, salary_max=26000)) == 1.0
    assert scoring.salary_fraction(candidate, make_job(salary_min=15000, salary_max=22000)) == 0.7
    assert scoring.salary_fraction(candidate, make_job(salary_min=12000, salary_max=18000)) == 0.0
    assert scoring.salary_fraction(candidate, make_job(salary_min=None, salary_max=None)) == 0.5
    assert scoring.salary_fraction(candidate, make_job(salary_min=None, salary_max=25000)) == 1.0


def test_availability_fraction():
    all_open = make_job(vacancies=4, filled_positions=0)
    half_open_closing_today = make_job(vacancies=4, filled_positions=2, application_deadline=TODAY)
    assert scoring.availability_fraction(all_open, TODAY) == 1.0
    assert scoring.availability_fraction(half_open_closing_today, TODAY) == 0.25


# ---------- Final score ----------


def test_weights_add_up_to_100():
    assert sum(scoring.WEIGHTS.values()) == 100


def test_perfect_match_scores_100():
    result = scoring.score_job(make_candidate(), make_job(), TODAY)
    assert result["score"] == 100
    assert result["distance_km"] == 0


def test_score_is_the_sum_of_the_breakdown():
    job = make_job(employment_type="Part-time", work_mode="On-site", latitude=42.03, salary_min=15000)
    result = scoring.score_job(make_candidate(), job, TODAY)
    total = sum(row["points"] for row in result["score_breakdown"])
    assert result["score"] == pytest.approx(total, abs=0.05)
    assert 0 < result["score"] < 100


def test_same_input_gives_the_same_score():
    first = scoring.score_job(make_candidate(), make_job(), TODAY)
    second = scoring.score_job(make_candidate(), make_job(), TODAY)
    assert first == second


def test_visitor_with_only_location_and_skills_uses_three_criteria():
    visitor = Candidate(latitude=41.9981, longitude=21.4254, skills=["Python", "SQL", "Git"])
    result = scoring.score_job(visitor, make_job(), TODAY)
    criteria = [row["criterion"] for row in result["score_breakdown"]]
    assert criteria == ["skills", "distance", "availability"]
    assert result["score"] == 100  # 45 of 45 possible points


def test_reason_mentions_matched_skills():
    result = scoring.score_job(make_candidate(), make_job(), TODAY)
    assert result["reason"].startswith("Matches your Python, SQL and Git skills")


def test_job_without_matching_skills_is_kept_but_explained():
    candidate = make_candidate(skills=["Figma"])
    results = scoring.recommend(candidate, [make_job()], TODAY)
    assert len(results) == 1
    assert results[0]["score_breakdown"][0] == {"criterion": "skills", "points": 0.0, "max_points": 30}
    assert "None of the required skills match" in results[0]["reason"]


# ---------- Ranking ----------


def test_recommend_removes_closed_jobs_and_sorts_by_score():
    jobs = [
        make_job(id=1, required_skills=["Java", "Spring Boot"]),                   # weak match
        make_job(id=2),                                                            # perfect match
        make_job(id=3, application_deadline=TODAY - timedelta(days=3)),            # expired
        make_job(id=4, vacancies=1, filled_positions=1),                           # filled
        make_job(id=5, work_mode="On-site"),                                       # good match
    ]
    results = scoring.recommend(make_candidate(), jobs, TODAY)
    assert [item["job_id"] for item in results] == [2, 5, 1]
    scores = [item["score"] for item in results]
    assert scores == sorted(scores, reverse=True)


def test_ties_are_broken_by_deadline_and_then_by_id():
    jobs = [
        make_job(id=7),
        make_job(id=3),
        make_job(id=9, application_deadline=TODAY + timedelta(days=10)),  # earlier deadline
    ]
    results = scoring.recommend(make_candidate(), jobs, TODAY)
    assert [item["job_id"] for item in results] == [9, 3, 7]


def test_limit_cuts_the_list():
    jobs = [make_job(id=number) for number in range(1, 11)]
    assert len(scoring.recommend(make_candidate(), jobs, TODAY, limit=4)) == 4
