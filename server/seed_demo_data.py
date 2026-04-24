import argparse
import asyncio
import random
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select

from src.database import AsyncSessionLocal
from src.models.user import User, UserRole
from src.models.profile import Profile
from src.models.proof_signal import ProofSignal, SignalType
from src.models.appreciation import Appreciation
from src.services.auth_service import hash_password
from src.services.credibility_service import compute_and_save_score
from src.services.fraud_service import run_fraud_detection


PASSWORD = "SeedPass123!"

FIRST_NAMES = [
    "Ayaan", "Zara", "Hassan", "Maya", "Usman", "Nida", "Bilal", "Anaya", "Tariq", "Hina",
    "Faraz", "Sana", "Ibrahim", "Noor", "Ali", "Fatima", "Saad", "Mariam", "Daniyal", "Areeba",
]
LAST_NAMES = [
    "Khan", "Ahmed", "Malik", "Siddiqui", "Raza", "Qureshi", "Nawaz", "Iqbal", "Hussain", "Shah",
]
CITIES = ["Lahore, Pakistan", "Karachi, Pakistan", "Islamabad, Pakistan", "Rawalpindi, Pakistan", "Faisalabad, Pakistan"]
SKILL_POOL = [
    "React", "TypeScript", "Node.js", "FastAPI", "Python", "PostgreSQL", "Docker", "AWS",
    "Next.js", "Tailwind", "Redis", "GraphQL", "Django", "Vue", "MongoDB", "CI/CD",
]

EXPERIENCE_TEMPLATES = [
    {
        "title": "Frontend Engineer",
        "company": "PixelNest Labs",
        "description": "Built reusable React components and improved page speed by optimizing rendering and API usage.",
    },
    {
        "title": "Backend Developer",
        "company": "CloudForge Systems",
        "description": "Implemented FastAPI endpoints, optimized SQL queries, and added authentication + role permissions.",
    },
    {
        "title": "Full Stack Engineer",
        "company": "NovaStack",
        "description": "Delivered end-to-end features including dashboards, search flows, and notification pipelines.",
    },
    {
        "title": "Software Engineer",
        "company": "DataSpring",
        "description": "Maintained production systems, fixed critical bugs, and wrote automated integration tests.",
    },
]

PORTFOLIO_TEMPLATES = [
    {
        "title": "B2B Analytics Dashboard",
        "description": "Created a multi-tenant analytics dashboard with role-based access and exportable reports.",
        "url": "https://example.com/analytics",
    },
    {
        "title": "E-commerce Admin Panel",
        "description": "Built inventory, order, and fulfillment workflows with audit logs and alerting.",
        "url": "https://example.com/admin",
    },
    {
        "title": "Hiring Workflow Portal",
        "description": "Implemented profile scoring, candidate search ranking, and recruiter collaboration flows.",
        "url": "https://example.com/hiring",
    },
    {
        "title": "Messaging Platform",
        "description": "Developed threaded messaging with unread counts and polling-based updates.",
        "url": "https://example.com/messages",
    },
]

FEEDBACK_STRONG = [
    "Delivered every milestone on schedule and communicated clearly. Code quality was high and easy to maintain.",
    "Very reliable engineer. Handled changing requirements professionally and kept us updated throughout.",
    "Great technical execution and excellent collaboration with our product team. Would hire again.",
]

FEEDBACK_MIXED = [
    "Communication was good, but some parts needed refactoring before release.",
    "Project was completed, though a few deadlines slipped. Overall still helpful.",
    "Strong coding ability, but updates could have been more proactive.",
]

FEEDBACK_GENERIC = [
    "Great work, highly recommend!",
    "Amazing freelancer, would hire again!",
    "Perfect work, 10/10, great communication!",
]


async def _next_uid(db, cache: dict[str, int]) -> int:
    """Generate deterministic uid values when DB default sequence is unavailable."""
    if "value" not in cache:
        max_uid = (await db.execute(select(func.max(User.uid)))).scalar_one_or_none()
        cache["value"] = int(max_uid or 1000)
    cache["value"] += 1
    return cache["value"]


def _pick_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def _skills(rng: random.Random, count: int) -> list[str]:
    return rng.sample(SKILL_POOL, k=max(0, min(count, len(SKILL_POOL))))


def _experience(rng: random.Random, count: int) -> list[dict]:
    rows = []
    for _ in range(count):
        tpl = rng.choice(EXPERIENCE_TEMPLATES)
        start_year = rng.randint(2018, 2024)
        start_month = rng.randint(1, 12)
        current = rng.random() < 0.35
        end_year = rng.randint(start_year, 2026)
        end_month = rng.randint(1, 12)
        rows.append(
            {
                "id": str(uuid.uuid4())[:8],
                "title": tpl["title"],
                "company": tpl["company"],
                "start_date": f"{start_year:04d}-{start_month:02d}",
                "end_date": None if current else f"{end_year:04d}-{end_month:02d}",
                "current": current,
                "description": tpl["description"],
            }
        )
    return rows


def _portfolio(rng: random.Random, count: int) -> list[dict]:
    rows = []
    for _ in range(count):
        tpl = rng.choice(PORTFOLIO_TEMPLATES)
        rows.append(
            {
                "id": str(uuid.uuid4())[:8],
                "title": tpl["title"],
                "description": tpl["description"],
                "url": tpl["url"],
                "tech_stack": _skills(rng, rng.randint(2, 5)),
            }
        )
    return rows


def _proof_signals_for_tier(tier: str) -> list[tuple[SignalType, str, str | None, str | None]]:
    if tier in {"elite", "full", "strong"}:
        return [
            (SignalType.github, "GitHub Profile", "https://github.com/example-dev", None),
            (SignalType.portfolio_link, "Live Portfolio", "https://portfolio.example.dev", None),
            (SignalType.client_reference, "Client Reference", None, "A previous client praised delivery and communication."),
            (SignalType.screenshot, "Dashboard Screenshot", None, "Sample dashboard screen from production project."),
        ]
    if tier in {"good", "average"}:
        return [
            (SignalType.github, "GitHub Profile", "https://github.com/example-dev", None),
            (SignalType.client_reference, "Reference", None, "Reference available on request."),
        ]
    if tier == "light":
        return [
            (SignalType.portfolio_link, "Project Link", "https://example.com/project", None),
        ]
    return []


def _tier_profile_data(rng: random.Random, tier: str) -> dict:
    base = {
        "title": None,
        "location": None,
        "bio": None,
        "skills": [],
        "experience": [],
        "portfolio": [],
        "profile_views": rng.randint(0, 40),
    }

    if tier == "elite":
        base.update(
            {
                "title": "Principal Full-Stack Engineer",
                "location": rng.choice(CITIES),
                "bio": "I build secure, scalable web products end-to-end with a focus on delivery reliability, clean architecture, and measurable business impact.",
                "skills": _skills(rng, 8),
                "experience": _experience(rng, 3),
                "portfolio": _portfolio(rng, 3),
                "profile_views": rng.randint(120, 320),
            }
        )
    elif tier == "full":
        base.update(
            {
                "title": "Senior Software Engineer",
                "location": rng.choice(CITIES),
                "bio": "Experienced engineer delivering production-grade apps using modern frontend and backend stacks.",
                "skills": _skills(rng, 6),
                "experience": _experience(rng, 2),
                "portfolio": _portfolio(rng, 2),
                "profile_views": rng.randint(90, 220),
            }
        )
    elif tier == "strong":
        base.update(
            {
                "title": "Full-Stack Developer",
                "location": rng.choice(CITIES),
                "bio": "I focus on dependable delivery, clear communication, and writing maintainable code.",
                "skills": _skills(rng, 5),
                "experience": _experience(rng, 2),
                "portfolio": _portfolio(rng, 1),
                "profile_views": rng.randint(70, 180),
            }
        )
    elif tier == "good":
        base.update(
            {
                "title": "Backend Developer",
                "location": rng.choice(CITIES),
                "bio": "Backend-focused developer with practical API and database experience.",
                "skills": _skills(rng, 4),
                "experience": _experience(rng, 1),
                "portfolio": _portfolio(rng, 1),
            }
        )
    elif tier == "average":
        base.update(
            {
                "title": "Frontend Developer",
                "location": rng.choice(CITIES),
                "bio": "I build UI features and collaborate with teams to ship releases.",
                "skills": _skills(rng, 3),
                "experience": _experience(rng, 1),
                "portfolio": [],
            }
        )
    elif tier == "light":
        base.update(
            {
                "title": "Junior Developer",
                "location": rng.choice(CITIES),
                "bio": "Entry-level developer learning fast and contributing to web projects.",
                "skills": _skills(rng, 2),
                "experience": [],
                "portfolio": [],
            }
        )
    elif tier == "junior":
        base.update(
            {
                "title": "Associate Developer",
                "location": rng.choice(CITIES),
                "bio": "I recently started freelancing and am building my portfolio.",
                "skills": _skills(rng, 2),
            }
        )
    elif tier == "bare":
        base.update(
            {
                "title": "Developer",
                "location": rng.choice(CITIES),
                "bio": "Available for projects.",
                "skills": _skills(rng, 1),
            }
        )
    elif tier == "minimal":
        base.update(
            {
                "title": None,
                "location": None,
                "bio": "",
                "skills": [],
            }
        )
    elif tier == "empty":
        base.update(
            {
                "title": None,
                "location": None,
                "bio": None,
                "skills": [],
                "experience": [],
                "portfolio": [],
                "profile_views": 0,
            }
        )

    return base


async def seed_demo_data(prefix: str, clients: int, candidates: int, reset_prefix: bool, random_seed: int | None) -> None:
    rng = random.Random(random_seed)
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")

    tiers = ["elite", "full", "strong", "good", "average", "light", "junior", "bare", "minimal", "empty"]
    while len(tiers) < candidates:
        tiers.append(rng.choice(["good", "average", "light", "minimal"]))
    tiers = tiers[:candidates]

    async with AsyncSessionLocal() as db:
        uid_cache: dict[str, int] = {}

        if reset_prefix:
            existing = (await db.execute(select(User).where(User.email.like(f"{prefix}.%@seed.local")))).scalars().all()
            if existing:
                ids = [u.id for u in existing]
                await db.execute(delete(Appreciation).where(Appreciation.from_user_id.in_(ids) | Appreciation.to_user_id.in_(ids)))
                await db.execute(delete(User).where(User.id.in_(ids)))
                await db.commit()

        created_clients: list[User] = []
        created_candidates: list[User] = []

        # Clients
        for i in range(clients):
            name = _pick_name(rng)
            email = f"{prefix}.client{i+1}.{stamp}@seed.local"
            user = User(
                uid=await _next_uid(db, uid_cache),
                email=email,
                hashed_password=hash_password(PASSWORD),
                full_name=name,
                role=UserRole.client,
            )
            db.add(user)
            created_clients.append(user)

        # Candidates with profile quality tiers
        for i in range(candidates):
            tier = tiers[i]
            name = _pick_name(rng)
            email = f"{prefix}.pro{i+1}.{tier}.{stamp}@seed.local"
            user = User(
                uid=await _next_uid(db, uid_cache),
                email=email,
                hashed_password=hash_password(PASSWORD),
                full_name=name,
                role=UserRole.candidate,
            )
            db.add(user)
            await db.flush()

            profile_data = _tier_profile_data(rng, tier)
            profile = Profile(
                user_id=user.id,
                bio=profile_data["bio"],
                title=profile_data["title"],
                location=profile_data["location"],
                skills=profile_data["skills"],
                experience=profile_data["experience"],
                portfolio=profile_data["portfolio"],
                profile_views=profile_data["profile_views"],
            )
            db.add(profile)
            await db.flush()

            for sig_type, sig_title, sig_url, sig_desc in _proof_signals_for_tier(tier):
                db.add(
                    ProofSignal(
                        profile_id=profile.id,
                        signal_type=sig_type,
                        title=sig_title,
                        url=sig_url,
                        description=sig_desc,
                    )
                )

            created_candidates.append(user)

        await db.commit()

        # Create sample appreciations across quality levels
        if created_clients and created_candidates:
            for idx, cand in enumerate(created_candidates):
                reviewer = created_clients[idx % len(created_clients)]
                if idx <= 2:
                    text = rng.choice(FEEDBACK_STRONG)
                elif idx <= 6:
                    text = rng.choice(FEEDBACK_MIXED)
                else:
                    text = rng.choice(FEEDBACK_GENERIC)

                if "Perfect work" in text:
                    skill, comm, rel = 10.0, 10.0, 10.0
                elif "great" in text.lower() or "reliable" in text.lower():
                    skill, comm, rel = 8.5, 8.8, 8.6
                elif "slipped" in text.lower() or "refactoring" in text.lower():
                    skill, comm, rel = 6.8, 7.8, 6.2
                else:
                    skill, comm, rel = 7.0, 7.0, 7.0

                db.add(
                    Appreciation(
                        to_user_id=cand.id,
                        from_user_id=reviewer.id,
                        raw_feedback=text,
                        summary=text[:180],
                        skill_rating=skill,
                        communication_rating=comm,
                        reliability_rating=rel,
                    )
                )

            # Add extra generic reviews to last candidate for fraud-risk scenario
            if len(created_candidates) >= 1:
                low_target = created_candidates[-1]
                for text in FEEDBACK_GENERIC:
                    reviewer = rng.choice(created_clients)
                    db.add(
                        Appreciation(
                            to_user_id=low_target.id,
                            from_user_id=reviewer.id,
                            raw_feedback=text,
                            summary=text,
                            skill_rating=10.0,
                            communication_rating=10.0,
                            reliability_rating=10.0,
                        )
                    )

            await db.commit()

    # Compute score + fraud flags after seed inserts
    for cand in created_candidates:
        await compute_and_save_score(cand.id)
        await run_fraud_detection(cand.id)

    print("\nSeed completed successfully")
    print(f"Created clients: {len(created_clients)}")
    print(f"Created candidates: {len(created_candidates)}")
    print(f"Default password for all seeded accounts: {PASSWORD}\n")

    print("Client accounts:")
    for c in created_clients:
        print(f"- {c.full_name} | {c.email}")

    print("\nCandidate accounts (tiered):")
    for i, c in enumerate(created_candidates):
        print(f"- tier={tiers[i]:7s} | {c.full_name} | {c.email}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed HireCred demo users and profiles.")
    parser.add_argument("--prefix", default="demo", help="Email prefix namespace, e.g. demo")
    parser.add_argument("--clients", type=int, default=2, help="Number of client accounts")
    parser.add_argument("--candidates", type=int, default=10, help="Number of candidate accounts")
    parser.add_argument("--reset-prefix", action="store_true", help="Delete existing seeded users with the same prefix before inserting")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for reproducibility")
    args = parser.parse_args()

    if args.clients < 1 or args.candidates < 1:
        raise SystemExit("Both --clients and --candidates must be >= 1")

    await seed_demo_data(
        prefix=args.prefix,
        clients=args.clients,
        candidates=args.candidates,
        reset_prefix=args.reset_prefix,
        random_seed=args.seed,
    )


if __name__ == "__main__":
    asyncio.run(main())
