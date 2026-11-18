"""Reset the database and load seed data.

    uv run python -m app.seed           # departments, categories, wards, users
    uv run python -m app.seed --demo    # ... plus 20 demo complaints in various states

WARNING: drops every table and deletes uploaded media first.
Every seeded account uses the password Demo@123.
"""

import argparse
import shutil
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.config import settings
from app.db import Base, SessionLocal, engine, utcnow
from app.models import Category, Complaint, Department, Role, Status, Upvote, User, Ward
from app.security import hash_password
from app.services import complaints as workflow
from app.services.ml import classifier

PASSWORD = "Demo@123"

DEPARTMENTS = [
    ("ROADS", "Roads & Infrastructure", "Potholes, damaged roads and footpaths"),
    ("WATER", "Water Supply", "Water supply, leakage and water quality"),
    ("SEWER", "Sewerage & Drainage", "Sewers, drains and waterlogging"),
    ("SANITATION", "Sanitation & Waste Management", "Garbage collection, street cleaning"),
    ("ELECTRICITY", "Electricity & Streetlights", "Streetlights and electrical hazards"),
    ("HORTICULTURE", "Parks & Horticulture", "Trees, parks and green belts"),
    ("HEALTH", "Public Health", "Mosquito control and stray animals"),
    ("ENFORCEMENT", "Enforcement & Planning", "Encroachment, illegal construction, noise"),
]

# code, name, department, weight (0-2), SLA hours. Codes = ML labels.
CATEGORIES = [
    ("road_damage", "Pothole / Damaged Road", "ROADS", 1, 72),
    ("no_water", "No / Low Water Supply", "WATER", 1, 24),
    ("water_leakage", "Water Pipeline Leakage", "WATER", 1, 48),
    ("dirty_water", "Contaminated Water", "WATER", 2, 24),
    ("sewer_overflow", "Sewer Overflow / Blocked Drain", "SEWER", 2, 24),
    ("waterlogging", "Waterlogging", "SEWER", 1, 48),
    ("garbage", "Garbage Not Collected", "SANITATION", 1, 48),
    ("dead_animal", "Dead Animal Removal", "SANITATION", 1, 24),
    ("streetlight", "Streetlight Not Working", "ELECTRICITY", 1, 72),
    ("electric_hazard", "Hanging Wires / Electrical Hazard", "ELECTRICITY", 2, 12),
    ("tree_fall", "Fallen / Dangerous Tree", "HORTICULTURE", 2, 24),
    ("park_maintenance", "Park Maintenance", "HORTICULTURE", 0, 168),
    ("mosquito", "Mosquito Breeding / Fogging", "HEALTH", 1, 72),
    ("stray_animals", "Stray Animals", "HEALTH", 1, 72),
    ("encroachment", "Encroachment", "ENFORCEMENT", 0, 168),
    ("illegal_construction", "Illegal Construction", "ENFORCEMENT", 0, 168),
    ("noise_pollution", "Noise Pollution", "ENFORCEMENT", 0, 72),
]

# Approximate demo boundaries (lat_min, lat_max, lng_min, lng_max), not official wards.
WARDS = [
    ("W1", "Ward 1 - Noida Central (Sector 18 area)", (28.555, 28.595, 77.300, 77.350)),
    ("W2", "Ward 2 - Noida Sector 62 / IT Hub", (28.600, 28.645, 77.350, 77.390)),
    ("W3", "Ward 3 - Greater Noida West", (28.580, 28.625, 77.410, 77.460)),
    ("W4", "Ward 4 - Greater Noida (Pari Chowk & Knowledge Park)", (28.440, 28.490, 77.475, 77.535)),
]

FIRST = ["Rajesh", "Sunita", "Amit", "Neha", "Vikram", "Pooja", "Sanjay", "Kavita",
         "Rahul", "Anjali", "Manoj", "Deepa", "Arun", "Ritu", "Suresh", "Meena"]
LAST = ["Kumar", "Sharma", "Singh", "Verma", "Gupta", "Yadav", "Chauhan", "Tyagi",
        "Mishra", "Rawat", "Bhati", "Nagar", "Saxena", "Joshi", "Pandey", "Malik"]

HOME = (28.4660, 77.5090, "Near Pari Chowk, Greater Noida")  # citizens' saved location


def reset_db() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    for sub in ("complaints", "proof"):
        shutil.rmtree(settings.media_dir / sub, ignore_errors=True)


def seed_base(db: Session) -> None:
    depts = {code: Department(code=code, name=name, description=desc) for code, name, desc in DEPARTMENTS}
    db.add_all(depts.values())
    db.add_all(
        Category(code=code, name=name, department=depts[dept], weight=weight, sla_hours=sla)
        for code, name, dept, weight, sla in CATEGORIES
    )

    wards = []
    for code, name, (lat0, lat1, lng0, lng1) in WARDS:
        polygon = [[lat0, lng0], [lat0, lng1], [lat1, lng1], [lat1, lng0]]
        wards.append(
            Ward(code=code, name=name, polygon=polygon, center_lat=(lat0 + lat1) / 2, center_lng=(lng0 + lng1) / 2)
        )
    db.add_all(wards)

    pw = hash_password(PASSWORD)
    i = 0
    for ward in wards:
        for dept in depts.values():
            db.add(
                User(
                    name=f"{FIRST[i % 16]} {LAST[(i * 7 + i // 16) % 16]}",
                    email=f"{dept.code.lower()}.{ward.code.lower()}@gp.demo",
                    password_hash=pw,
                    role=Role.OFFICER,
                    department=dept,
                    ward=ward,
                )
            )
            i += 1
    db.add(User(name="Portal Admin", email="admin@gp.demo", password_hash=pw, role=Role.ADMIN))
    for n, name in enumerate(["Aarav Sharma", "Priya Verma"], start=1):
        db.add(
            User(
                name=name, email=f"citizen{n}@gp.demo", password_hash=pw, role=Role.CITIZEN,
                lat=HOME[0], lng=HOME[1], address=HOME[2],
            )
        )
    db.commit()

    labels = set(classifier.labels)
    codes = {c[0] for c in CATEGORIES}
    if labels != codes:
        print(f"WARNING: model labels and categories differ: {sorted(labels ^ codes)}")


# who, text, severity, lat, lng, address, days ago, final state, "me too" votes
DEMO = [
    ("citizen1", "Bahut bada gaddha hai Pari Chowk ke paas service road par, raat ko bike wale gir rahe hain", "high", 28.4669, 77.5128, "Service road near Pari Chowk", 6, "in_progress", 4),
    ("citizen2", "Streetlights on the Knowledge Park II main road are not working for a week, the stretch is completely dark and unsafe for students", "high", 28.4592, 77.4968, "Knowledge Park II main road", 5, "assigned", 3),
    ("n1", "Garbage has not been collected from C block for 5 days, dustbins are overflowing and stray dogs are spreading it", "medium", 28.4735, 77.5098, "C Block, Alpha 1", 4, "open", 2),
    ("n2", "Sewer overflowing near Beta 1 market, ganda paani sadak par aa raha hai aur badbu bahut hai", "high", 28.4612, 77.5165, "Beta 1 market", 3, "open", 5),
    ("citizen2", "Paani nahi aa raha 2 din se hamare block mein, tanki khali hai", "high", 28.4780, 77.5060, "Alpha 2", 2, "open", 3),
    ("n3", "Bijli ke taar latak rahe hain Knowledge Park III bus stop ke paas, bacche wahan khelte hain", "critical", 28.4718, 77.4842, "Near Knowledge Park III bus stop", 1, "open", 2),
    ("citizen1", "A big tree has fallen across the lane after last night's storm and is blocking the road", "high", 28.4545, 77.5075, "Lane 4, Beta 2", 9, "resolved", 1),
    ("n4", "Machhar bahut ho gaye hain, dengue ke case aa rahe hain society mein, fogging karwao", "medium", 28.4630, 77.5020, "Beta 2 housing society", 7, "resolved", 2),
    ("n1", "Water pipeline is leaking near the metro station, clean water has been flowing on the road for 3 days", "medium", 28.4652, 77.5105, "Near Pari Chowk metro station", 3, "assigned", 1),
    ("n5", "Stray cattle sitting in the middle of the road near the market, causing traffic jams every evening", "medium", 28.4705, 77.5160, "Jagat Farm market road", 2, "open", 0),
    ("n2", "Rehri patri walon ne footpath par kabza kar liya hai, paidal chalne ki jagah nahi hai", "low", 28.4690, 77.5140, "Jagat Farm market footpath", 9, "rejected", 0),
    ("n3", "Loud DJ music from the banquet hall every night past midnight, nobody can sleep", "low", 28.4585, 77.5110, "Banquet hall, Beta 1", 4, "in_progress", 1),
    ("citizen2", "Dead dog lying on the road near the metro station for two days, very bad smell", "medium", 28.4570, 77.4985, "Near Knowledge Park II metro", 1, "open", 0),
    ("n4", "The park has broken swings and overgrown grass, children cannot play there", "low", 28.4745, 77.5075, "Central park, Alpha 1", 10, "resolved", 0),
    ("n5", "Severe waterlogging outside the college gate after rain, students walking through dirty water", "medium", 28.4730, 77.4870, "College gate, Knowledge Park III", 6, "resolved", 2),
    ("citizen1", "Please help, someone needs to look into this issue in our area", "medium", 28.4650, 77.5050, "Beta 1", 1, "open", 0),
    ("n1", "Huge potholes on the road near Sector 18 market, cars are getting damaged", "medium", 28.5705, 77.3215, "Sector 18 market, Noida", 3, "open", 0),
    ("n2", "Nal se ganda kala paani aa raha hai, peene layak nahi hai", "high", 28.5760, 77.3300, "Sector 27, Noida", 2, "open", 0),
    ("n3", "Someone is burning garbage near Gaur Chowk, smoke everywhere", "high", 28.6045, 77.4345, "Gaur Chowk, Greater Noida West", 1, "open", 0),
    ("n4", "Streetlight not working outside my house", "medium", 28.6315, 77.2167, "Connaught Place, New Delhi", 2, "open", 0),
]

STEPS = {  # final state -> workflow steps (hours after submission)
    "open": [],
    "assigned": [("pick", 5)],
    "in_progress": [("pick", 4), ("progress", 20)],
    "resolved": [("pick", 3), ("progress", 18), ("resolve", 50)],
    "rejected": [("pick", 6), ("reject", 8)],
}


def seed_demo(db: Session) -> None:
    pw = hash_password(PASSWORD)
    users = {u.email.split("@")[0]: u for u in db.scalars(select(User).where(User.role == Role.CITIZEN))}
    for n in range(1, 6):
        u = User(name=f"Neighbour {n}", email=f"neighbour{n}@gp.demo", password_hash=pw, role=Role.CITIZEN,
                 lat=HOME[0], lng=HOME[1], address=HOME[2])
        db.add(u)
        users[f"n{n}"] = u
    db.commit()
    voters = list(users.values())

    now = utcnow()
    for who, text, severity, lat, lng, address, days, state, votes in DEMO:
        t0 = now - timedelta(days=days, hours=3)
        c = workflow.create_complaint(db, users[who], text, severity, lat, lng, address, [], created_at=t0)
        route = f"{c.category.code if c.category else '-'} -> {c.ward.code if c.ward else '-'}"
        print(f"  {c.ticket_no}  {c.status:<8} {route:<28} {text[:50]}")

        if c.status == Status.TRIAGE:
            continue
        officer = db.scalar(
            select(User).where(User.role == Role.OFFICER, User.department_id == c.department_id, User.ward_id == c.ward_id)
        )
        for step, hours in STEPS[state]:
            at = min(t0 + timedelta(hours=hours), now - timedelta(minutes=5))
            if step == "pick":
                workflow.pick(db, officer, c)
                c.assigned_at = at
            elif step == "progress":
                workflow.set_in_progress(db, officer, c, "Team dispatched to the site")
            elif step == "resolve":
                workflow.resolve(db, officer, c, "Work completed and site inspected.", [])
                c.resolved_at = at
            elif step == "reject":
                workflow.reject(db, officer, c, "Weekly market is permitted here on Tuesdays; vendors are cleared after hours.")
            db.flush()
            c.history[-1].created_at = at
            c.updated_at = at

        for voter in [v for v in voters if v.id != c.citizen_id][:votes]:
            db.add(Upvote(complaint_id=c.id, user_id=voter.id, created_at=t0 + timedelta(hours=8)))
            c.upvote_count += 1
        workflow.recompute_priority(c)
        db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--demo", action="store_true", help="also add demo complaints")
    args = parser.parse_args()

    print(f"Resetting database: {settings.database_url}")
    reset_db()
    classifier.load()
    with SessionLocal() as db:
        seed_base(db)
        if args.demo:
            print("Adding demo complaints:")
            seed_demo(db)
        counts = {m.__tablename__: db.query(m).count() for m in (Department, Category, Ward, User, Complaint)}
    print("Done:", ", ".join(f"{v} {k}" for k, v in counts.items()))
    print(f"\nAll accounts use password {PASSWORD}")
    print("  citizen1@gp.demo, citizen2@gp.demo   admin@gp.demo")
    print("  officers: <department>.<ward>@gp.demo, e.g. roads.w4@gp.demo, sewer.w4@gp.demo")


if __name__ == "__main__":
    main()
