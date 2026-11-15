"""Recommendation logic: deterministic, rule-based scoring (no machine learning).

How it works
------------
1. Jobs that cannot be applied for are removed (see ``is_eligible``).
2. Every remaining job is checked against ten criteria. Each criterion returns a
   fraction between 0.0 (no fit) and 1.0 (perfect fit).
3. fraction x weight = points for that criterion. The weights add up to 100.
4. The points are added together, which gives a score from 0 to 100.
5. Jobs are sorted from the highest score to the lowest.

A criterion returns ``None`` when the candidate did not give the information that
is needed for it (this happens on ``GET /recommendations?lat=..&lon=..&skills=..``,
where only location and skills are known). Such a criterion is skipped and the
score is calculated only from the criteria that could be checked.

This file has no database code. Every function only needs a candidate object and
a job object, so the rules are easy to read and easy to test.
"""

from datetime import date, time
from math import asin, cos, radians, sin, sqrt

# ---------------------------------------------------------------------------
# Settings of the scoring formula (all design decisions are in this block)
# ---------------------------------------------------------------------------

# Maximum points per criterion. The sum is 100.
WEIGHTS = {
    "skills": 30,           # required skills that the candidate has
    "interests": 10,        # job category is one of the candidate's interests
    "audience": 10,         # job targets the candidate's study area
    "year_of_study": 5,     # can a student in this year take this type of job
    "employment_type": 10,  # internship / part-time / full-time preference
    "schedule": 5,          # working hours fit the candidate's availability
    "work_mode": 5,         # on-site / hybrid / remote preference
    "distance": 10,         # how far the workplace is (Haversine)
    "salary": 10,           # salary range against the minimum expected salary
    "availability": 5,      # open positions and time left until the deadline
}

# Value of target_audience that means "open to every study area".
OPEN_AUDIENCE = "All Graduates"
OPEN_AUDIENCE_FRACTION = 0.7  # open to everyone, but not aimed at this candidate

# Expected working hours for each employment type (the dataset has no schedule field).
EXPECTED_SCHEDULE = {
    "Full-time": (time(9, 0), time(17, 0)),
    "Internship": (time(9, 0), time(15, 0)),
    "Part-time": (time(9, 0), time(13, 0)),
}

# Ordered from "always at the office" to "never at the office".
WORK_MODES = ["On-site", "Hybrid", "Remote"]

# Distance at which the distance points drop to zero. Hybrid jobs need fewer
# trips to the office, so a longer distance is still acceptable.
MAX_DISTANCE_KM = {"On-site": 30.0, "Hybrid": 60.0}
CLOSE_DISTANCE_KM = 5.0  # used only for the text "is close to your location"

SALARY_IN_RANGE_FRACTION = 0.7  # expectation is inside the advertised range
SALARY_UNKNOWN_FRACTION = 0.5   # the job does not advertise a salary

DEADLINE_COMFORT_DAYS = 7  # with a week or more left there is enough time to apply

EARTH_RADIUS_KM = 6371.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in kilometres between two points on the Earth (Haversine formula)."""
    lat1, lon1, lat2, lon2 = radians(lat1), radians(lon1), radians(lat2), radians(lon2)
    d_lat = lat2 - lat1
    d_lon = lon2 - lon1
    a = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def normalize(values) -> set[str]:
    """Turn a list of words into a set of lower-case words, so 'python' == 'Python '."""
    return {value.strip().lower() for value in (values or []) if value.strip()}


def minutes(moment: time) -> int:
    """Minutes since midnight, e.g. 09:30 -> 570."""
    return moment.hour * 60 + moment.minute


def join_words(words: list[str]) -> str:
    """['A', 'B', 'C'] -> 'A, B and C'."""
    if len(words) == 1:
        return words[0]
    return ", ".join(words[:-1]) + " and " + words[-1]


def matched_skills(candidate, job) -> list[str]:
    """Required skills that the candidate has, in the order they are listed in the job."""
    candidate_skills = normalize(candidate.skills)
    return [skill for skill in job.required_skills if skill.strip().lower() in candidate_skills]


def distance_km(candidate, job) -> float | None:
    """Distance between candidate and workplace. None for remote jobs (nobody travels)."""
    if job.work_mode == "Remote":
        return None
    if candidate.latitude is None or candidate.longitude is None:
        return None
    return haversine_km(candidate.latitude, candidate.longitude, job.latitude, job.longitude)


# ---------------------------------------------------------------------------
# Eligibility: jobs that are never recommended
# ---------------------------------------------------------------------------


def is_eligible(job, today: date) -> bool:
    """A job can be recommended only if it is active, not expired and not filled."""
    if job.deleted_at is not None:         # soft-deleted listing
        return False
    if job.application_deadline < today:   # deadline has passed
        return False
    if job.available_positions <= 0:       # every vacancy is already filled
        return False
    return True


# ---------------------------------------------------------------------------
# The ten criteria. Each returns a fraction 0.0-1.0, or None when it cannot be checked.
# ---------------------------------------------------------------------------


def skills_fraction(candidate, job) -> float:
    """Share of the required skills that the candidate has (2 of 3 -> 0.67)."""
    required = normalize(job.required_skills)
    if not required:
        return 1.0  # nothing is required, so nothing is missing
    return len(required & normalize(candidate.skills)) / len(required)


def interests_fraction(candidate, job) -> float | None:
    """1.0 when the job category is one of the candidate's interests."""
    interests = normalize(candidate.interests)
    if not interests:
        return None
    return 1.0 if job.category.strip().lower() in interests else 0.0


def audience_fraction(candidate, job) -> float | None:
    """Does the job target the candidate's study area, or is it open to everyone?"""
    if not candidate.study_area:
        return None
    audience = job.target_audience.strip().lower()
    if audience == candidate.study_area.strip().lower():
        return 1.0
    if audience == OPEN_AUDIENCE.lower():
        return OPEN_AUDIENCE_FRACTION
    return 0.0  # the job is aimed at a different study area


def year_of_study_fraction(candidate, job) -> float | None:
    """Internships and part-time jobs suit every year. Full-time jobs suit
    final-year students and graduates, because lectures take most of the day."""
    year = candidate.year_of_study
    if year is None:
        return None
    if job.employment_type != "Full-time":
        return 1.0
    if year >= 4:
        return 1.0
    if year == 3:
        return 0.5
    return 0.0


def employment_type_fraction(candidate, job) -> float | None:
    """Preferred employment type. Internship and part-time are similar (both can be
    combined with studying), so they give half of the points for each other."""
    preferred = candidate.preferred_employment_type
    if not preferred:
        return None
    if job.employment_type == preferred:
        return 1.0
    if {job.employment_type, preferred} == {"Internship", "Part-time"}:
        return 0.5
    return 0.0


def schedule_fraction(candidate, job) -> float | None:
    """Share of the expected working hours during which the candidate is available.

    Example: full-time is 09:00-17:00 (8 hours). A candidate available 10:00-18:00
    covers 10:00-17:00 = 7 hours, so the fraction is 7 / 8 = 0.875.
    """
    if candidate.available_from is None or candidate.available_to is None:
        return None
    work_start, work_end = EXPECTED_SCHEDULE[job.employment_type]
    overlap_start = max(minutes(work_start), minutes(candidate.available_from))
    overlap_end = min(minutes(work_end), minutes(candidate.available_to))
    overlap = max(overlap_end - overlap_start, 0)
    return overlap / (minutes(work_end) - minutes(work_start))


def work_mode_fraction(candidate, job) -> float | None:
    """Same work mode -> 1.0, one step away (e.g. Hybrid vs Remote) -> 0.5,
    opposite (On-site vs Remote) -> 0.0."""
    preferred = candidate.preferred_work_mode
    if not preferred:
        return None
    steps = abs(WORK_MODES.index(job.work_mode) - WORK_MODES.index(preferred))
    return 1 - steps / 2


def distance_fraction(job, distance: float | None) -> float | None:
    """Remote jobs get full points (no travel). For on-site and hybrid jobs the
    points fall in a straight line from 1.0 at 0 km to 0.0 at the maximum distance."""
    if job.work_mode == "Remote":
        return 1.0
    if distance is None:
        return None
    return max(0.0, 1 - distance / MAX_DISTANCE_KM[job.work_mode])


def salary_fraction(candidate, job) -> float | None:
    """Compare the advertised salary range with the candidate's minimum salary."""
    expected = candidate.min_salary
    if expected is None:
        return None
    # If only one end of the range is given, use it for both ends.
    lowest = job.salary_min if job.salary_min is not None else job.salary_max
    highest = job.salary_max if job.salary_max is not None else job.salary_min
    if lowest is None:
        return SALARY_UNKNOWN_FRACTION    # salary is not advertised
    if lowest >= expected:
        return 1.0                        # even the lowest offer is enough
    if highest >= expected:
        return SALARY_IN_RANGE_FRACTION   # possible, but not guaranteed
    return 0.0                            # even the highest offer is too low


def availability_fraction(job, today: date) -> float:
    """Average of two parts:
    - share of the vacancies that are still open (2 of 4 -> 0.5)
    - time left: 1.0 with a week or more, less when the deadline is very close
    """
    open_share = job.available_positions / job.vacancies if job.vacancies > 0 else 0.0
    days_left = (job.application_deadline - today).days
    time_left = max(0.0, min(days_left / DEADLINE_COMFORT_DAYS, 1.0))
    return (open_share + time_left) / 2


# ---------------------------------------------------------------------------
# Final score, explanation text and ranking
# ---------------------------------------------------------------------------


def build_reason(candidate, job, fractions: dict, distance: float | None) -> str:
    """Short sentence that explains the recommendation, built from the same facts as the score."""
    matched = matched_skills(candidate, job)
    phrases = []

    if matched:
        phrases.append(f"matches your {join_words(matched)} skills")
    if fractions["interests"] == 1.0:
        phrases.append(f"fits your interest in {job.category}")
    if job.work_mode == "Remote":
        phrases.append("is fully remote")
    elif distance is not None and distance <= CLOSE_DISTANCE_KM:
        phrases.append("is close to your location")
    if fractions["salary"] == 1.0:
        phrases.append("meets your salary expectation")
    if fractions["employment_type"] == 1.0:
        phrases.append(f"is the employment type you prefer ({job.employment_type})")
    if fractions["audience"] == 1.0:
        phrases.append(f"targets {job.target_audience} students")

    if phrases:
        sentence = join_words(phrases[:4])  # the four most important facts are enough
        reason = sentence[0].upper() + sentence[1:] + "."
    else:
        reason = "Still open for applications, but only a weak match for your profile."

    if not matched:
        reason += " None of the required skills match your profile yet."
    return reason


def score_job(candidate, job, today: date) -> dict:
    """Score one job for one candidate."""
    distance = distance_km(candidate, job)

    fractions = {
        "skills": skills_fraction(candidate, job),
        "interests": interests_fraction(candidate, job),
        "audience": audience_fraction(candidate, job),
        "year_of_study": year_of_study_fraction(candidate, job),
        "employment_type": employment_type_fraction(candidate, job),
        "schedule": schedule_fraction(candidate, job),
        "work_mode": work_mode_fraction(candidate, job),
        "distance": distance_fraction(job, distance),
        "salary": salary_fraction(candidate, job),
        "availability": availability_fraction(job, today),
    }

    earned = 0.0    # points the job collected
    possible = 0    # points it could collect (weights of the criteria that were checked)
    breakdown = []
    for criterion, fraction in fractions.items():
        if fraction is None:
            continue  # no information for this criterion -> it is not counted
        weight = WEIGHTS[criterion]
        points = round(weight * fraction, 1)
        earned += points
        possible += weight
        breakdown.append({"criterion": criterion, "points": points, "max_points": weight})

    return {
        "score": round(100 * earned / possible, 1),
        "score_breakdown": breakdown,
        "distance_km": round(distance, 2) if distance is not None else None,
        "reason": build_reason(candidate, job, fractions, distance),
    }


def recommend(candidate, jobs, today: date, limit: int = 20) -> list[dict]:
    """Return the best jobs for a candidate, sorted from the highest score to the lowest."""
    results = []
    for job in jobs:
        if not is_eligible(job, today):
            continue
        result = score_job(candidate, job, today)
        results.append(
            {
                "job_id": job.id,
                "title": job.title,
                "category": job.category,
                "employer": job.employer,
                "employment_type": job.employment_type,
                "work_mode": job.work_mode,
                "location_name": job.location_name,
                "salary_min": job.salary_min,
                "salary_max": job.salary_max,
                "application_deadline": job.application_deadline,
                "available_positions": job.available_positions,
                **result,
            }
        )

    # Highest score first. Ties are broken by the earlier deadline and then by the
    # job id, so the same input always produces exactly the same order.
    results.sort(key=lambda item: (-item["score"], item["application_deadline"], item["job_id"]))
    return results[:limit]
