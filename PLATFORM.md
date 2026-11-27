# Trivium Learn — Learn-Anything Platform (on top of trivium-ai)

Fork of [F3LP5/trivium-ai](https://github.com/F3LP5/trivium-ai) (MIT).
The AI course engine is untouched — this layer adds the product on top:
public catalog by skill category, Fog-of-War progression, gamification,
spaced repetition, and a mastery certificate.

## What was added

| Area | Where | What |
| ---- | ----- | ---- |
| Catalog | `backend/app/services/catalog.py`, `GET /api/catalog`, `GET /api/catalog/categories` | 10 skill categories (Code, Music, Money, Business, Mind & Logic, Design, Language, Craft, Science, Life), deterministic keyword classifier, search + category filter. Cards show **topic / category / difficulty only**. |
| Fog-of-War | `GET /api/courses/{id}`, `GET /api/courses/{id}/next-step`, locked-lesson `403` | Inside a course the API returns **only the current step + completed steps**. Future module/lesson titles, counts (`total_modules`, `total_lessons`) and `progress_percent` are stripped server-side. Direct access to a locked lesson returns `403` with no title leak. |
| Trivium gates | `GET /api/lessons/{id}/gates` | Grammar (MCQ mastery) → Logic (simulation / discursive) → Rhetoric (Socratic duel). Unlock only fires when all gates pass (`check_and_unlock_lesson`, unchanged). |
| Gamification | `GET /api/profile/stats`, `POST /api/profile/activity` | XP (25 per completed lesson, 10 per review), level ring, streak, badges. Computed **only from completed work** — never from future totals. |
| Spaced repetition | `GET /api/reviews/due`, `POST /api/reviews/{id}/complete` | Missed quizzes queue a review due tomorrow; completing doubles the interval. |
| Certificate | `GET /api/courses/{id}/certificate` | Unlocks only when every step is completed; returns a share URL. |
| UI | `frontend/src/app/page.tsx`, `frontend/src/app/course/[id]/page.tsx` | Catalog section with category chips + search, gamification chip in the header, course page rewritten as a single blind "current step" card + mastered-steps review list. No roadmap, no counts, no SkillTree. |

### Generation tiers, personas and retention UI

- **Tiers:** `/api/catalog/tiers` publishes the exact contract Basic 4×3 (12),
  Working 8×4 (32), Mastery 12×5 (60). The home level picker sends the tier id
  (`basic`/`working`/`mastery`); the API resolves it to a canonical level before
  the orchestrator reads `LEVEL_SPECS`, so English and Portuguese sessions get
  the same course size. `backend/tests/test_catalog_tiers.py` pins the sizes,
  aliases, personas and upload citations (7 tests).
- **Personas:** `/api/catalog/personas` exposes `auto`, `practitioner`,
  `socratic`, `storyteller`, `rigorist`. The picker is available in both web and
  upload modes and the chosen voice overrides the AI-inferred mentor profile.
- **Retention UI:** XP / level ring / streak / badges render in the header of
  home, course and lesson pages; passing a gate fires `notifyProfileUpdated()`
  so the panel refreshes immediately. Confetti fires on MCQ, simulation and
  Socratic passes. Chapter-level citations from uploaded PDF/EPUB render as
  non-link source chips with page ranges.
- **Blind step:** the course page reads `/api/courses/{id}/current-step` (title,
  hook, stage) instead of the blind `/next-step` pointer, so the single revealed
  card has content without exposing future steps.

### Rhetoric Express, exports and mastery report

- **Build & Present:** after the two-round Socratic duel, `GET|POST /api/lessons/{id}/mini-project`
  serves a lesson-scoped brief, grades the learner's artifact (LLM when configured,
  deterministic rubric offline), and persists it in the same per-user
  `socratic_state_json` used by the duel. No schema change and no cross-lesson
  content: the brief is built from the current lesson's `core_concept` only.
- **Exports:** `GET /api/lessons/{id}/export-notes` produces a Markdown booklet
  with the lesson text, the learner's teach-back answers and the mini-project;
  `GET /api/lessons/{id}/download-pdf` remains the editorial PDF. Both are
  authenticated and refuse locked lessons.
- **Dashboard report:** `GET /api/dashboard/mastery/report` downloads the
  post-hoc mastery view (earned work and due reviews only) from the same
  fog-safe data source as `/api/dashboard/mastery`.
- **Mobile:** the lesson header wraps to two rows below 640px, labels/zoom
  collapse to icons, and the tutor sidebar is full-width inside the viewport.
  Retrieval practice always renders alongside a Logic simulation, so the
  Grammar gate stays completable, and the Express brief appears as soon as the
  teach-back duel is passed (no reload). The full loop is covered by
  `backend/tests/test_e2e_loop.py` (Learn → Quiz → Simulate → Teach-back →
  Express → Unlock, tutor scoping and both exports).

Engine files intentionally **not modified**: `backend/app/agents/pipeline.py`,
`backend/app/services/researcher.py`, `backend/app/schemas/curriculum.py`,
`backend/app/schemas/quiz.py`, `backend/app/graph/orchestrator.py`.

Auth is a single local learner profile (singleton DB row) — the DB is the
sync layer; swapping in real multi-user auth means scoping `LearnerProfile`
by user id later.

## Run

```bash
# backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --port 8000

# frontend
cd frontend && npm install && npm run dev   # NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Tests

```bash
cd backend && python -m pytest tests/test_platform.py -q
```

The test seeds a course with secret future titles and asserts the API never
leaks them (nor any total/percent), that gates enforce Grammar → Logic →
Rhetoric before unlock, and that XP only counts completed lessons.
