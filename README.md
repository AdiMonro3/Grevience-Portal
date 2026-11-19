# Grievance Portal

Citizens report civic problems (potholes, garbage, sewer overflow, hanging wires…) in English or Hinglish, with photos and a map location. An ML model picks the category, a ward lookup finds the area, and the complaint lands in the right officer's queue, sorted by priority. Officers pick it up, update the status and resolve it with proof photos. The citizen gets an email at every step.

**Stack:** FastAPI · SQLAlchemy · SQLite (PostgreSQL later) · JWT (python-jose + passlib) · scikit-learn · SMTP via BackgroundTasks · React (Vite) · React Router · Axios · Tailwind CSS · React-Leaflet + OpenStreetMap

---

## Quick start

You need [uv](https://docs.astral.sh/uv/) (Python 3.13) and Node 20+.

```bash
# 1. Backend  ->  http://localhost:8000/docs
cd backend
uv sync
cp .env.example .env               # optional: set JWT_SECRET and Gmail settings
uv run python -m app.seed --demo   # resets the DB, loads wards/officers + 20 demo complaints
uv run uvicorn app.main:app --reload

# 2. Frontend  ->  http://localhost:5173   (second terminal)
cd frontend
npm install
npm run dev
```

The ML model trains itself on first start, in about 3 seconds. To retrain by hand, run `uv run python -m app.ml.train`.

### Demo accounts (password `Demo@123`)

| Role | Email |
|---|---|
| Citizen | `citizen1@gp.demo`, `citizen2@gp.demo` (home: Pari Chowk, Greater Noida) |
| Officer | `<department>.<ward>@gp.demo`, e.g. `sewer.w4@gp.demo`, `roads.w4@gp.demo`, `electricity.w1@gp.demo` |
| Admin | `admin@gp.demo` |

Departments: `roads`, `water`, `sewer`, `sanitation`, `electricity`, `horticulture`, `health`, `enforcement`. Wards: `w1` to `w4`. The login page has one-click buttons for the main demo accounts.

### Real emails

Without SMTP settings, emails are printed in the API console, so everything still works. To send real ones:

1. Turn on 2-Step Verification on a Gmail account, then create an **App password** (Google Account → Security → App passwords).
2. In `backend/.env`, set `SMTP_USER=<that gmail>` and `SMTP_PASSWORD=<16-char app password>`.
3. Seeded users have fake `@gp.demo` addresses. Either register a new citizen with your real email, or set `EMAIL_OVERRIDE_TO=<your inbox>` to receive every email there (best for the projector).

### Sign in with Google (optional)

Login and sign-up show a **Sign in with Google** button once a client ID is set. Without one, the button is hidden.

1. [Google Cloud Console](https://console.cloud.google.com/) → create a project → **Google Auth Platform** (APIs & Services → OAuth consent screen). Choose *External*, fill in the app name and support email, and under **Audience** add the Gmail accounts you'll demo with as *test users*. In *Testing* mode, only test users can sign in.
2. **Clients** → *Create client* → **Web application**. Under *Authorized JavaScript origins*, add `http://localhost:5173` **and** `http://localhost`. You don't need a redirect URI or the client secret.
3. Put the client ID in `backend/.env` as `GOOGLE_CLIENT_ID=….apps.googleusercontent.com`, then restart the API.
4. Open the app at `http://localhost:5173`. Google rejects `127.0.0.1` unless you add that origin as well.

How it works: Google's button gives the browser a signed ID token. `POST /auth/google` checks the token's signature against Google's public keys, then checks that the token is for this client ID, was issued by Google, hasn't expired, and has a verified email.
- **First Google sign-in:** creates a citizen account.
- **Email matches an existing account:** links to it, so seeded users can try Google too if their email is a real Google account.
- **Later sign-ins:** matched by Google's account ID.

After signing up with email and password, the user is sent to the login page to log in. Signing up with Google logs them in right away, since Google has already confirmed who they are.

---

## Demo script

Log in as `citizen1@gp.demo` in one browser and `sewer.w4@gp.demo` in a private window.

1. **Citizen, Nearby.** Shows issues within 3 km as a list or a map. Tap **Me too** on one: it raises that ticket's priority.
2. **Citizen, Report issue.** Type the Hinglish complaint below, pick *High*, attach a photo, and submit. The success screen shows the ticket number, the detected category (with confidence), the department and the ward. The "Complaint received" email arrives.
3. **Officer, My queue.** The new ticket appears (the queue auto-refreshes every 20 s), sorted by priority, then oldest first. Open it to see the description, photo, map pin, and the AI routing details (confidence, urgency reasons). Press **Pick up**: the citizen gets the officer's name and email. Press **Mark in progress**, then **Resolve** with a note and a proof photo.
4. **Citizen, My complaints.** Open the ticket. It shows Resolved with the proof photo and the full timeline: Submitted → Open → Officer assigned → In progress → Resolved. Show the four emails in the inbox.
5. **Triage.** As the citizen, go to **My location**, choose *Connaught Place (outside service area)*, and submit anything, or submit the vague complaint below from Pari Chowk. Log in as `admin@gp.demo`: **Triage** shows why each ticket is there, with the model's suggestion pre-filled. Pick a ward and press **Route**.

| Scripted complaint | Expected result |
|---|---|
| `Hamari gali mein naali band ho gayi hai, ganda paani ghar ke andar aa raha hai, bacche bimar ho rahe hain` | Sewer Overflow → Sewerage & Drainage, Ward 4, urgent (`sewer.w4`) |
| `Live electric wire hanging low near the bus stop, sparks come out when it rains` | Electrical Hazard → Electricity (`electricity.w4`) |
| `Sadak par bahut bada gaddha hai, kal raat ek scooter wala gir gaya` | Pothole → Roads (`roads.w4`) |
| `Kooda 4 din se nahi utha, poori gali mein badbu aa rahi hai` | Garbage → Sanitation (`sanitation.w4`) |
| `Bhai sahab kuch karo yahan, bahut pareshani hai` | Too vague → **Triage** (about 11% confidence) |

Re-run `uv run python -m app.seed --demo` before the demo to start clean.

**Offline fallback:** map tiles and address search need internet. Every map has a list or text equivalent, and the *Quick pick a locality* buttons set a location without any network.

---

## How routing works

On `POST /complaints`, in a single request:

1. **Media** is checked (≤ 3 photos at 5 MB, 1 video at 25 MB, JPG/PNG/WEBP/HEIC/MP4/WEBM/MOV) and saved with random file names.
2. **ML** ([backend/app/services/ml.py](backend/app/services/ml.py)): TF-IDF over words + character n-grams (handles Hinglish spellings like *paani/pani*) → logistic regression over 17 categories. Urgency 1–3 comes from keyword rules (injury, live wire, children, open manhole, "4 din se", smell…), and the matched reasons are shown to the officer.
3. **Geo** ([backend/app/services/geo.py](backend/app/services/geo.py)): a point-in-polygon check finds the ward.
4. If confidence < 0.5, or no ward is found, the status is **TRIAGE**. Otherwise the category sets the department, the ward is set, and the status is **OPEN**.
5. **Priority** ([backend/app/services/priority.py](backend/app/services/priority.py)) = 20 × severity + 10 × urgency + 5 × category weight + 3 × "Me too" votes (max 30). P1 ≥ 100, P2 ≥ 75, P3 ≥ 55.
6. The ticket number (`GRV-26-00021`) and history rows are written, and the "received" email is queued as a background task.

The status rules live in one place, [backend/app/services/complaints.py](backend/app/services/complaints.py): `TRIAGE → OPEN → ASSIGNED → IN_PROGRESS → RESOLVED`, and `REJECTED` (reason required) from any open state. Officers can only see or act on tickets in their own department + ward. Outside it they get a 404, so they can't probe other wards' ticket numbers.

Model accuracy: on sentences it has never seen (grouped 5-fold CV), the baseline is about 61% across 17 categories. Clear complaints usually score above 80% confidence. Unclear ones fall below 0.5 and go to triage, which is the safety net. Phase 4 improves the model.

## API

Open `/docs` and use **Authorize** with a demo account.

| | |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/google`, `GET /auth/providers`, `GET /auth/me`, `PUT /users/me/location` |
| Reference | `GET /categories`, `/departments`, `/wards`, `/geo/ward`, `/geo/geocode`, `/geo/reverse` |
| Citizen | `POST /complaints` (multipart), `GET /complaints/mine`, `GET /complaints/nearby`, `GET /complaints/{t}`, `GET /complaints/{t}/history`, `POST /complaints/{t}/upvote` |
| Officer | `GET /officer/queue`, `GET /officer/complaints/{t}`, `POST …/pick`, `PATCH …/status`, `POST …/resolve` (multipart) |
| Admin | `GET /admin/triage`, `PATCH /admin/complaints/{t}/assign`, `POST /admin/complaints/{t}/reject` |

## Project layout

```
backend/app/
  main.py  config.py  db.py  deps.py  security.py  seed.py
  models/    SQLAlchemy tables (users, departments, categories, wards, complaints, media, history, upvotes)
  schemas/   Pydantic request/response models
  routers/   auth, meta, complaints, officer, admin
  services/  ml, geo, priority, email, storage, complaints (workflow)
  ml/        training_data.py, train.py -> model.joblib
backend/media/      uploaded files (served at /media)
frontend/src/
  api/client.js       axios + JWT + error messages
  auth/AuthContext.jsx
  components/         StatusBadge, Timeline, MediaUpload, MediaGallery, MapView, ComplaintView, ProtectedRoute, Layout, Modal
  pages/citizen/      Location, Nearby, NewComplaint, Submitted, MyComplaints, ComplaintDetail
  pages/officer/      Queue, TicketDetail
  pages/admin/        Triage
```

## Known limitations (demo build)

- Ward boundaries are rough rectangles around Noida / Greater Noida, not official boundaries.
- Uploaded media is served publicly by its random URL (no auth on `/media`).
- Tables are created on startup. There are no migrations yet.
- A failed email is only logged, never retried.

## Roadmap

**Phase 3: complete the product**
- [ ] Citizen reopen (`POST /complaints/{t}/reopen`) with a reason
- [ ] Admin CRUD for departments, wards, categories, officers + admin panel UI
- [ ] SLA deadlines (`categories.sla_hours` is already stored) + a scheduled escalation job
- [ ] Email retry + email log table; rate limiting on submit
- [ ] PostgreSQL + Alembic; real ward shapes with shapely
- [ ] Map view in the officer queue; loading/empty/error polish everywhere

**Phase 4: deeper AI + analytics**
- [ ] Duplicate detection on submit ("12 similar complaints nearby, add a Me too instead?")
- [ ] Export admin corrections to `backend/app/ml/data/extra.csv` (already picked up by `train.py`) + retrain
- [ ] Multilingual embeddings / MuRIL vs. this baseline
- [ ] Analytics endpoints + dashboard (by ward/category, resolution time, SLA breaches), hotspot map

**Phase 5: quality + deployment**
- [ ] pytest for routing, jurisdiction, status transitions, priority
- [ ] Docker + docker-compose (API + Postgres), S3 storage, structured logs
- [ ] Deploy the frontend (Vercel/Netlify, `VITE_API_URL`) and the API (Render/Railway); GitHub Actions CI
