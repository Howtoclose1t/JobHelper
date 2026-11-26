"""Local skill matching and application tracking."""

import re
import sqlite3
import unicodedata
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path


STATUSES = ("Saved", "Applied", "Interview", "Offer", "Rejected", "Withdrawn")
COMPANY_SUFFIXES = {"corp", "gmbh", "inc", "limited", "llc", "ltd", "plc"}
TITLE_MODIFIERS = {"junior", "jr", "senior", "sr", "remote", "hybrid"}
SKILL_ALIASES = {
    "aws": ("amazon web services",),
    "postgresql": ("postgres",),
    "scikit-learn": ("sklearn", "scikit learn"),
    "spark": ("pyspark", "apache spark"),
}
DEMO_SKILLS = "Python, SQL, dbt, PostgreSQL, Docker"
DEMO_JOBS = (
    ("Northstar Example Labs", "Data Engineer", "Build data pipelines using Python, SQL, dbt, Airflow, and Spark.", "Applied"),
    ("Harbor Example Analytics", "Analytics Engineer", "Own dbt models and build reports with SQL and PostgreSQL. Experience with Tableau is helpful.", "Interview"),
)
DEMO_CHECK = ("Northstar Example Labs, Inc.", "Junior Data Engineer", DEMO_JOBS[0][2])


@dataclass(frozen=True)
class DemoPosting:
    source: str
    company: str
    title: str
    location: str
    description: str


DEMO_SOURCES = ("StepStone", "LinkedIn", "XING", "EnglishJobs.de", "Jobs Without German")
DEMO_POSTINGS = (
    DemoPosting("StepStone", *DEMO_CHECK[:2], "Berlin", DEMO_CHECK[2]),
    DemoPosting("StepStone", "Cedar Example Systems", "Machine Learning Engineer", "Munich", "Train Python models with scikit-learn and ship services using Docker."),
    DemoPosting("LinkedIn", *DEMO_JOBS[1][:2], "Hamburg", DEMO_JOBS[1][2]),
    DemoPosting("XING", "Juniper Example Works", "Backend Engineer", "Berlin", "Build Python APIs with PostgreSQL and Docker."),
    DemoPosting("EnglishJobs.de", "Maple Example Studio", "Data Analyst", "Remote", "Use SQL and Tableau to report product metrics."),
    DemoPosting("Jobs Without German", "Alder Example Robotics", "Computer Vision Engineer", "Munich", "Build image processing pipelines using Python and OpenCV."),
)


def normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def words(value: str) -> list[str]:
    return re.findall(r"[^\W_]+", normalize(value))


def search_demo(source: str, query: str, location: str) -> list[DemoPosting]:
    keywords = set(words(query))
    places = set(words(location))
    return [posting for posting in DEMO_POSTINGS
            if (source == "All sources" or posting.source == source)
            and keywords.issubset(words(f"{posting.title} {posting.company} {posting.description}"))
            and places.issubset(words(posting.location))]


def company_key(value: str) -> tuple[str, ...]:
    tokens = words(value)
    while len(tokens) > 1 and tokens[-1] in COMPANY_SUFFIXES:
        tokens.pop()
    return tuple(tokens)


def title_key(value: str) -> frozenset[str]:
    tokens = frozenset(words(value))
    return tokens - TITLE_MODIFIERS or tokens


@dataclass(frozen=True)
class SkillMatch:
    matched: tuple[str, ...]
    unmentioned: tuple[str, ...]

    @property
    def percent(self) -> int:
        total = len(self.matched) + len(self.unmentioned)
        return round(100 * len(self.matched) / total) if total else 0


def match_skills(skills: str, description: str) -> SkillMatch:
    labels: dict[str, str] = {}
    for part in re.split(r"[,\n]", skills):
        label = " ".join(part.split())
        if label:
            labels.setdefault(normalize(label), label)

    text = normalize(description)
    matched, unmentioned = [], []
    for key, label in labels.items():
        terms = (key, *SKILL_ALIASES.get(key, ()))
        found = any(re.search(rf"(?<!\w){re.escape(term)}(?![\w+#])", text) for term in terms)
        (matched if found else unmentioned).append(label)
    return SkillMatch(tuple(matched), tuple(unmentioned))


@dataclass(frozen=True)
class Application:
    id: int
    company: str
    title: str
    description: str
    status: str
    added_on: str


def new_application(company: str, title: str, description: str, record_id: int = 0) -> Application:
    company, title, description = company.strip(), title.strip(), description.strip()
    if not company_key(company) or not title_key(title) or not description:
        raise ValueError("Enter a company, job title, and job description.")
    return Application(record_id, company, title, description, STATUSES[0], date.today().isoformat())


def duplicate_candidates(company: str, title: str, records: list[Application]) -> list[Application]:
    company_tokens = company_key(company)
    role_tokens = title_key(title)
    if not company_tokens or not role_tokens:
        return []
    return [record for record in records
            if company_tokens == company_key(record.company) and role_tokens == title_key(record.title)]


class Tracker:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY, company TEXT NOT NULL, title TEXT NOT NULL,
                description TEXT NOT NULL, status TEXT NOT NULL, added_on TEXT NOT NULL
            )""")

    @contextmanager
    def _connection(self):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            yield connection

    def list(self) -> list[Application]:
        with self._connection() as connection:
            rows = connection.execute("""SELECT id, company, title, description, status, added_on
                                         FROM applications ORDER BY id DESC""").fetchall()
        return [Application(*row) for row in rows]

    def add(self, company: str, title: str, description: str) -> int:
        record = new_application(company, title, description)
        with self._connection() as connection:
            result = connection.execute("""INSERT INTO applications (company, title, description, status, added_on)
                                  VALUES (?, ?, ?, ?, ?)""",
                               (record.company, record.title, record.description, record.status, record.added_on))
            return int(result.lastrowid)

    def set_status(self, record_id: int, status: str) -> None:
        if status not in STATUSES:
            raise ValueError("Choose a valid application status.")
        with self._connection() as connection:
            result = connection.execute("UPDATE applications SET status = ? WHERE id = ?", (status, record_id))
            if not result.rowcount:
                raise ValueError("This application no longer exists.")
