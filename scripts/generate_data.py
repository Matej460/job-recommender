"""Generate the synthetic datasets.

Creates:
    data/raw/jobs.csv      - 150 valid jobs + 9 intentionally broken rows
    data/candidates.csv    - 80 candidate profiles

Run:  uv run python -m scripts.generate_data

The random generator uses a fixed seed, so the script always creates the same
jobs and candidates. Only the application deadlines change: they are calculated
from today's date, so the dataset always contains open jobs on the day it is run.
All employers and candidates are fictional.
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
NUMBER_OF_JOBS = 150
NUMBER_OF_CANDIDATES = 80

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
JOBS_FILE = DATA_DIR / "raw" / "jobs.csv"
CANDIDATES_FILE = DATA_DIR / "candidates.csv"

JOB_COLUMNS = [
    "job_id", "title", "description", "category", "employer", "location_name",
    "latitude", "longitude", "employment_type", "work_mode", "required_skills",
    "target_audience", "salary_min", "salary_max", "application_deadline",
    "vacancies", "filled_positions",
]
CANDIDATE_COLUMNS = [
    "candidate_id", "name", "email", "study_area", "year_of_study", "latitude",
    "longitude", "skills", "interests", "preferred_employment_type",
    "preferred_work_mode", "available_from", "available_to", "min_salary",
]

OPEN_AUDIENCE = "All Graduates"

# category -> role -> (study area the role targets, skills of the role)
# The first two skills of a role are always required, the others are optional extras.
CATEGORIES = {
    "Software Development": {
        "Python Developer": ("Computer Science", ["Python", "SQL", "Git", "REST APIs", "Docker"]),
        "Java Developer": ("Computer Science", ["Java", "SQL", "Git", "Spring Boot", "REST APIs"]),
        "Frontend Developer": ("Computer Science", ["JavaScript", "HTML", "CSS", "React", "Git"]),
        "QA Engineer": ("Computer Science", ["Testing", "SQL", "Git", "Python", "Attention to Detail"]),
        "Mobile Developer": ("Computer Science", ["Kotlin", "Java", "Git", "REST APIs", "UI Design"]),
    },
    "Data Analytics": {
        "Data Analyst": ("Computer Science", ["Python", "SQL", "Excel", "Power BI", "Statistics"]),
        "BI Analyst": ("Mathematics", ["SQL", "Power BI", "Excel", "Data Visualization", "Reporting"]),
        "Data Engineer": ("Computer Science", ["Python", "SQL", "Git", "Docker", "ETL"]),
    },
    "Marketing": {
        "Digital Marketing Specialist": ("Marketing", ["Social Media", "SEO", "Google Analytics", "Content Writing", "Communication"]),
        "Content Creator": ("Marketing", ["Content Writing", "Social Media", "Canva", "Copywriting", "Communication"]),
        "Marketing Assistant": ("Economics", ["Social Media", "Communication", "Excel", "Email Marketing", "Canva"]),
    },
    "Business": {
        "Business Analyst": ("Business Administration", ["Excel", "Business Analysis", "Communication", "Presentation Skills", "SQL"]),
        "Operations Assistant": ("Business Administration", ["Excel", "Organization", "Communication", "Reporting", "Problem Solving"]),
        "Market Researcher": ("Economics", ["Market Research", "Excel", "Presentation Skills", "Statistics", "Communication"]),
    },
    "Design": {
        "UI/UX Designer": ("Graphic Design", ["Figma", "UI Design", "UX Research", "Prototyping", "Communication"]),
        "Graphic Designer": ("Graphic Design", ["Adobe Photoshop", "Adobe Illustrator", "Canva", "Typography", "Creativity"]),
    },
    "Finance": {
        "Financial Analyst": ("Finance", ["Excel", "Financial Analysis", "Accounting", "Reporting", "Attention to Detail"]),
        "Accountant": ("Finance", ["Accounting", "Excel", "Budgeting", "Attention to Detail", "Reporting"]),
        "Audit Assistant": ("Economics", ["Accounting", "Excel", "Attention to Detail", "Communication", "Reporting"]),
    },
    "Human Resources": {
        "HR Assistant": ("Psychology", ["Communication", "Recruitment", "Organization", "Excel", "Onboarding"]),
        "Recruiter": ("Business Administration", ["Recruitment", "Interviewing", "Communication", "Organization", "English"]),
    },
    "Customer Support": {
        # No specific study area: these jobs are always open to everyone.
        "Customer Support Agent": (None, ["Communication", "English", "Problem Solving", "CRM", "Customer Service"]),
        "Technical Support Agent": (None, ["Communication", "English", "Troubleshooting", "Problem Solving", "CRM"]),
    },
    "Engineering": {
        "Electrical Engineer": ("Electrical Engineering", ["Circuit Design", "MATLAB", "AutoCAD", "PLC Programming", "Problem Solving"]),
        "Mechanical Engineer": ("Mechanical Engineering", ["SolidWorks", "AutoCAD", "Technical Drawing", "MATLAB", "Problem Solving"]),
        "Automation Engineer": ("Electrical Engineering", ["PLC Programming", "Python", "Circuit Design", "Problem Solving", "AutoCAD"]),
    },
    "Project Management": {
        "Project Coordinator": ("Business Administration", ["Planning", "Communication", "Excel", "Organization", "Jira"]),
        "Scrum Master": ("Computer Science", ["Agile", "Scrum", "Jira", "Communication", "Leadership"]),
    },
    "Sales": {
        "Sales Representative": ("Economics", ["Communication", "Negotiation", "CRM", "Customer Service", "English"]),
        "Account Manager": ("Marketing", ["Communication", "Negotiation", "CRM", "Presentation Skills", "Excel"]),
    },
    "Research": {
        "Research Assistant": ("Psychology", ["Academic Writing", "Statistics", "Excel", "Data Analysis", "Literature Review"]),
        "Survey Analyst": ("Mathematics", ["Statistics", "SPSS", "Excel", "Data Analysis", "Surveys"]),
    },
}

# Some categories have more job ads than others (a higher number = more jobs).
CATEGORY_WEIGHTS = {
    "Software Development": 3, "Data Analytics": 2, "Marketing": 2, "Business": 1.5,
    "Design": 1.5, "Finance": 1.5, "Human Resources": 1, "Customer Support": 1.5,
    "Engineering": 1.5, "Project Management": 1, "Sales": 1.5, "Research": 1,
}

# Fictional employers and the categories they hire for.
EMPLOYERS = {
    "TechNova": ["Software Development", "Data Analytics", "Project Management"],
    "CodeForge": ["Software Development", "Design"],
    "NexaSoft": ["Software Development", "Customer Support"],
    "CloudHarbor": ["Software Development", "Data Analytics"],
    "Vardar Systems": ["Software Development", "Engineering"],
    "DataBridge": ["Data Analytics", "Research"],
    "CoreMetrics": ["Data Analytics", "Business"],
    "Balkan Analytics": ["Data Analytics", "Research", "Business"],
    "InsightLab": ["Research", "Data Analytics", "Marketing"],
    "MarketLab": ["Marketing", "Sales"],
    "BlueRiver Media": ["Marketing", "Design"],
    "UrbanReach": ["Marketing", "Sales", "Customer Support"],
    "PixelPeak": ["Design", "Marketing"],
    "Lumen Studio": ["Design"],
    "Stonebridge Consulting": ["Business", "Project Management", "Finance"],
    "BrightPath": ["Business", "Human Resources"],
    "OptiTrade": ["Business", "Sales", "Finance"],
    "FinEdge": ["Finance"],
    "Polaris Finance": ["Finance", "Business"],
    "SkyLedger": ["Finance", "Data Analytics"],
    "PeopleFirst": ["Human Resources"],
    "TalentBridge": ["Human Resources", "Sales"],
    "HelpHub": ["Customer Support"],
    "RetailWave": ["Customer Support", "Sales", "Marketing"],
    "MechaWorks": ["Engineering"],
    "VoltLine": ["Engineering", "Project Management"],
    "SmartFactory": ["Engineering", "Software Development"],
    "GreenGrid Energy": ["Engineering", "Research"],
    "AgileNest": ["Project Management", "Software Development"],
    "Sunrise Logistics": ["Project Management", "Business", "Customer Support"],
    "SalesSprint": ["Sales"],
    "EduSpark": ["Research", "Human Resources"],
}

# (name, latitude, longitude, weight). Most offices and candidates are in Skopje.
LOCATIONS = [
    ("Skopje - Centar", 41.9961, 21.4317, 5),
    ("Skopje - Karpos", 42.0036, 21.3972, 5),
    ("Skopje - Aerodrom", 41.9847, 21.4661, 5),
    ("Skopje - Kisela Voda", 41.9747, 21.4420, 4),
    ("Skopje - Gazi Baba", 42.0158, 21.4722, 4),
    ("Skopje - Cair", 42.0114, 21.4411, 4),
    ("Skopje - Gjorce Petrov", 42.0075, 21.3539, 3),
    ("Tetovo", 42.0106, 20.9715, 1),
    ("Kumanovo", 42.1322, 21.7144, 1),
    ("Veles", 41.7153, 21.7753, 1),
    ("Bitola", 41.0297, 21.3292, 1),
    ("Ohrid", 41.1231, 20.8016, 1),
    ("Stip", 41.7458, 22.1958, 1),
]

EMPLOYMENT_TYPES = ["Internship", "Full-time", "Part-time"]
WORK_MODES = ["On-site", "Hybrid", "Remote"]

# Monthly salary in MKD: (lowest minimum, highest minimum, smallest range, largest range)
SALARY_RULES = {
    "Internship": (12000, 24000, 3000, 8000),
    "Part-time": (15000, 28000, 4000, 10000),
    "Full-time": (35000, 60000, 8000, 20000),
}

GENERAL_SKILLS = ["Communication", "English", "Excel", "Problem Solving", "Organization"]

MALE_NAMES = ["Marko", "Stefan", "Nikola", "Filip", "David", "Aleksandar", "Martin", "Luka",
              "Petar", "Bojan", "Daniel", "Viktor", "Kristijan", "Goran", "Damjan"]
FEMALE_NAMES = ["Ana", "Elena", "Marija", "Sara", "Ivana", "Teodora", "Mila", "Jovana",
                "Simona", "Kristina", "Angela", "Monika", "Viktorija", "Bojana", "Tamara"]
SURNAMES = ["Petrov", "Ivanov", "Stojanov", "Nikolov", "Trajkovski", "Dimitrov", "Jovanov",
            "Ristov", "Angelov", "Kostov", "Georgiev", "Popovski", "Mitrev", "Todorov",
            "Stefanovski", "Ilievski", "Spasov", "Velkov", "Naumov", "Bogdanov"]

# (available_from, available_to) options for candidates
AVAILABILITY = [("08:00", "16:00"), ("09:00", "17:00"), ("09:00", "15:00"), ("10:00", "18:00"),
                ("08:00", "13:00"), ("12:00", "20:00"), ("14:00", "20:00")]


def round_to_thousand(value: float) -> int:
    return int(round(value / 1000) * 1000)


def pick_location(rng: random.Random) -> tuple[str, float, float]:
    """Pick a place from LOCATIONS (places with a higher weight are picked more often)."""
    name, latitude, longitude, _ = rng.choices(LOCATIONS, weights=[place[3] for place in LOCATIONS])[0]
    return name, latitude, longitude


def build_offices(rng: random.Random) -> dict:
    """Give every employer one fixed office, a few hundred metres from the centre of the place."""
    offices = {}
    for employer in EMPLOYERS:
        name, latitude, longitude = pick_location(rng)
        offices[employer] = (
            name,
            round(latitude + rng.uniform(-0.004, 0.004), 4),
            round(longitude + rng.uniform(-0.004, 0.004), 4),
        )
    # The three employers from the example in the project brief keep their coordinates.
    offices["TechNova"] = ("Skopje - Centar", 41.9981, 21.4254)
    offices["MarketLab"] = ("Skopje - Centar", 41.9990, 21.4261)
    offices["DataBridge"] = ("Skopje - Centar", 41.9975, 21.4248)
    return offices


def job_title(role: str, employment_type: str) -> str:
    if employment_type == "Internship":
        return f"{role} Intern"
    if employment_type == "Part-time":
        return f"Part-time {role}"
    return f"Junior {role}"


def generate_jobs(rng: random.Random, today: date) -> list[dict]:
    offices = build_offices(rng)

    # The three example jobs from the project brief come first (ids 1-3).
    jobs = [
        {"title": "Junior Python Developer", "description": "Build backend APIs",
         "category": "Software Development", "employer": "TechNova",
         "employment_type": "Full-time", "work_mode": "Hybrid",
         "required_skills": ["Python", "SQL", "Git"], "target_audience": "Computer Science",
         "salary_min": 45000, "salary_max": 65000,
         "application_deadline": today + timedelta(days=45), "vacancies": 3, "filled_positions": 1},
        {"title": "Marketing Intern", "description": "Assist with digital campaigns",
         "category": "Marketing", "employer": "MarketLab",
         "employment_type": "Internship", "work_mode": "On-site",
         "required_skills": ["Social Media", "Communication", "Excel"], "target_audience": OPEN_AUDIENCE,
         "salary_min": 15000, "salary_max": 22000,
         "application_deadline": today + timedelta(days=50), "vacancies": 4, "filled_positions": 0},
        {"title": "Data Analyst Intern", "description": "Analyze business data",
         "category": "Data Analytics", "employer": "DataBridge",
         "employment_type": "Internship", "work_mode": "Remote",
         "required_skills": ["Python", "Excel", "SQL"], "target_audience": "Computer Science",
         "salary_min": 20000, "salary_max": 30000,
         "application_deadline": today + timedelta(days=57), "vacancies": 2, "filled_positions": 0},
    ]
    used = {(job["title"], job["employer"]) for job in jobs}  # avoids accidental duplicates

    while len(jobs) < NUMBER_OF_JOBS:
        category = rng.choices(list(CATEGORY_WEIGHTS), weights=list(CATEGORY_WEIGHTS.values()))[0]
        role = rng.choice(list(CATEGORIES[category]))
        study_area, role_skills = CATEGORIES[category][role]
        employment_type = rng.choices(EMPLOYMENT_TYPES, weights=[45, 30, 25])[0]
        title = job_title(role, employment_type)
        employer = rng.choice([name for name, hires in EMPLOYERS.items() if category in hires])
        if (title, employer) in used:
            continue  # this employer already has this ad, draw again
        used.add((title, employer))

        # 2 core skills + up to 2 of the other skills of the role
        required_skills = role_skills[:2] + rng.sample(role_skills[2:], k=rng.randint(0, 2))

        # About 65% of the jobs target one study area, the rest are open to everyone.
        if study_area is not None and rng.random() < 0.65:
            target_audience = study_area
        else:
            target_audience = OPEN_AUDIENCE

        # About 8% of the ads do not show a salary.
        if rng.random() < 0.08:
            salary_min = salary_max = None
        else:
            low, high, min_range, max_range = SALARY_RULES[employment_type]
            salary_min = round_to_thousand(rng.uniform(low, high))
            salary_max = salary_min + round_to_thousand(rng.uniform(min_range, max_range))

        # About 8% of the ads are already expired, the rest close in 3 to 90 days.
        if rng.random() < 0.08:
            deadline = today - timedelta(days=rng.randint(1, 30))
        else:
            deadline = today + timedelta(days=rng.randint(3, 90))

        # About 6% of the ads have no free position left.
        vacancies = rng.randint(1, 6)
        if rng.random() < 0.06:
            filled_positions = vacancies
        else:
            filled_positions = rng.randint(0, vacancies - 1)

        jobs.append({
            "title": title,
            "description": (
                f"Join {employer} in the role of {title}. You will work with "
                f"{required_skills[0]} and {required_skills[1]} in the {category} team."
            ),
            "category": category,
            "employer": employer,
            "employment_type": employment_type,
            "work_mode": rng.choices(WORK_MODES, weights=[45, 30, 25])[0],
            "required_skills": required_skills,
            "target_audience": target_audience,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "application_deadline": deadline,
            "vacancies": vacancies,
            "filled_positions": filled_positions,
        })

    # Turn the Python values into CSV text and add id + office location.
    rows = []
    for job_id, job in enumerate(jobs, start=1):
        location_name, latitude, longitude = offices[job["employer"]]
        rows.append({
            **job,
            "job_id": job_id,
            "location_name": location_name,
            "latitude": latitude,
            "longitude": longitude,
            "required_skills": ",".join(job["required_skills"]),
            "salary_min": "" if job["salary_min"] is None else job["salary_min"],
            "salary_max": "" if job["salary_max"] is None else job["salary_max"],
            "application_deadline": job["application_deadline"].isoformat(),
        })
    return rows


def add_dirty_rows(rows: list[dict]) -> list[dict]:
    """Make the raw file realistically messy, so the cleaning step has real work to do.

    Seven existing rows get a problem that can be FIXED (they stay in the dataset),
    and nine new rows are added that must be REJECTED.
    """
    # --- fixable problems ---
    rows[11]["employment_type"] = rows[11]["employment_type"].upper().replace("-", " ")  # "FULL TIME"
    rows[26]["work_mode"] = "  " + rows[26]["work_mode"].lower().replace("-", " ")       # "  on site"
    rows[57]["filled_positions"] = int(rows[57]["vacancies"]) + 2      # more filled than vacancies
    rows[95]["title"] = "  " + rows[95]["title"].replace(" ", "   ")   # extra spaces
    rows[109]["category"] = rows[109]["category"].lower()              # wrong letter case

    skills = rows[72]["required_skills"].split(",")                    # duplicates and empty items
    rows[72]["required_skills"] = f"{skills[0]} , {skills[0].lower()},, " + " ,".join(skills[1:])

    with_salary = next(row for row in rows[40:] if row["salary_min"] != "")
    with_salary["salary_min"], with_salary["salary_max"] = with_salary["salary_max"], with_salary["salary_min"]

    # --- rows that cannot be repaired ---
    def broken_copy(source_index: int, **changes) -> dict:
        return {**rows[source_index], **changes}

    bad_rows = [
        broken_copy(4),                                         # exact duplicate
        broken_copy(19, title=rows[19]["title"].upper()),       # duplicate with different letter case
        broken_copy(30, title=""),                              # missing title
        broken_copy(31, latitude="419.981"),                    # latitude out of range
        broken_copy(32, application_deadline="soon"),           # not a date
        broken_copy(33, employment_type="Volunteer"),           # unknown employment type
        broken_copy(34, vacancies=0),                           # no vacancies at all
        broken_copy(35, required_skills=""),                    # no required skills
        broken_copy(36, longitude="abc"),                       # longitude is not a number
    ]
    for offset, row in enumerate(bad_rows, start=1):
        row["job_id"] = len(rows) + offset
    return rows + bad_rows


def study_area_profile(study_area: str) -> tuple[list[str], list[str]]:
    """Skills and job categories that are typical for a study area (taken from CATEGORIES)."""
    skills, categories = [], []
    for category, roles in CATEGORIES.items():
        for target, role_skills in roles.values():
            if target == study_area:
                skills += [skill for skill in role_skills if skill not in skills]
                if category not in categories:
                    categories.append(category)
    return skills, categories


def generate_candidates(rng: random.Random) -> list[dict]:
    # The three example candidates from the project brief come first (ids 1-3).
    candidates = [
        {"name": "Ana Petrova", "email": "ana.pet@example.com", "study_area": "Computer Science",
         "year_of_study": 3, "latitude": 41.9980, "longitude": 21.4250,
         "skills": "Python,SQL,Git", "interests": "Software Development,Data Analytics",
         "preferred_employment_type": "Internship", "preferred_work_mode": "Hybrid",
         "available_from": "09:00", "available_to": "17:00", "min_salary": 20000},
        {"name": "Marko Ivanov", "email": "marko@example.com", "study_area": "Economics",
         "year_of_study": 4, "latitude": 41.9992, "longitude": 21.4262,
         "skills": "Excel,Communication,Social Media", "interests": "Marketing,Business",
         "preferred_employment_type": "Internship", "preferred_work_mode": "On-site",
         "available_from": "09:00", "available_to": "16:00", "min_salary": 15000},
        {"name": "Elena Stojanova", "email": "elena@example.com", "study_area": "Computer Science",
         "year_of_study": 2, "latitude": 41.9976, "longitude": 21.4249,
         "skills": "Python,Excel,SQL", "interests": "Data Analytics,Software Development",
         "preferred_employment_type": "Internship", "preferred_work_mode": "Remote",
         "available_from": "10:00", "available_to": "18:00", "min_salary": 18000},
    ]

    study_areas = sorted({target for roles in CATEGORIES.values() for target, _ in roles.values() if target})

    while len(candidates) < NUMBER_OF_CANDIDATES:
        candidate_id = len(candidates) + 1

        # Name (female surnames end with -a / -ska)
        surname = rng.choice(SURNAMES)
        if rng.random() < 0.5:
            first_name = rng.choice(FEMALE_NAMES)
            surname = surname[:-3] + "ska" if surname.endswith("ski") else surname + "a"
        else:
            first_name = rng.choice(MALE_NAMES)

        # Computer Science is the most common study area in this dataset.
        study_area = rng.choices(
            study_areas, weights=[3 if area == "Computer Science" else 1 for area in study_areas]
        )[0]
        area_skills, area_categories = study_area_profile(study_area)

        # 3-5 skills from the study area + sometimes one general skill
        skills = rng.sample(area_skills, k=min(rng.randint(3, 5), len(area_skills)))
        extra_skill = rng.choice(GENERAL_SKILLS)
        if rng.random() < 0.5 and extra_skill not in skills:
            skills.append(extra_skill)

        # 1-2 interests from the study area + sometimes one unrelated category
        interests = rng.sample(area_categories, k=min(rng.randint(1, 2), len(area_categories)))
        other_category = rng.choice(list(CATEGORIES))
        if rng.random() < 0.3 and other_category not in interests:
            interests.append(other_category)

        # Students in the first years mostly look for internships, graduates for full-time jobs.
        year_of_study = rng.randint(1, 5)  # 5 = recent graduate
        if year_of_study <= 3:
            type_weights = [60, 10, 30]
        elif year_of_study == 4:
            type_weights = [40, 40, 20]
        else:
            type_weights = [20, 65, 15]
        employment_type = rng.choices(EMPLOYMENT_TYPES, weights=type_weights)[0]

        # Expected salary is around the lower part of the typical range for that type.
        low, high, _, _ = SALARY_RULES[employment_type]
        min_salary = round_to_thousand(rng.uniform(low * 0.85, (low + high) / 2))

        _, latitude, longitude = pick_location(rng)
        available_from, available_to = rng.choice(AVAILABILITY)

        candidates.append({
            "name": f"{first_name} {surname}",
            "email": f"{first_name}.{surname}{candidate_id}@example.com".lower(),
            "study_area": study_area,
            "year_of_study": year_of_study,
            "latitude": round(latitude + rng.uniform(-0.01, 0.01), 4),   # home is about 1 km around
            "longitude": round(longitude + rng.uniform(-0.01, 0.01), 4),
            "skills": ",".join(skills),
            "interests": ",".join(interests),
            "preferred_employment_type": employment_type,
            "preferred_work_mode": rng.choices(WORK_MODES, weights=[35, 40, 25])[0],
            "available_from": available_from,
            "available_to": available_to,
            "min_salary": min_salary,
        })

    return [{"candidate_id": index, **candidate} for index, candidate in enumerate(candidates, start=1)]


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rng = random.Random(SEED)  # fixed seed -> the same data every time
    jobs = add_dirty_rows(generate_jobs(rng, date.today()))
    candidates = generate_candidates(rng)

    write_csv(JOBS_FILE, JOB_COLUMNS, jobs)
    write_csv(CANDIDATES_FILE, CANDIDATE_COLUMNS, candidates)

    print(f"Wrote {len(jobs)} raw job rows to {JOBS_FILE}")
    print(f"Wrote {len(candidates)} candidates to {CANDIDATES_FILE}")


if __name__ == "__main__":
    main()
