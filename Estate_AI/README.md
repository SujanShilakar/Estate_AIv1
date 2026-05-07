# Estate AI 

AI-powered property listing generator for real estate agents. Upload property photos → get a professional `realestate.com.au`-style listing and FB/IG ads in seconds.

This enhanced version adds:

- **Separate Agent and Admin login flows** with persistent SQLite-backed accounts
- **Agent dashboard** with sidebar nav: Dashboard / Generator / History
- **Admin console** for user management, generation history, compliance rules, listing templates, and usage analytics
- **Edit & save** support — edit generated listings/ads and save the changes back to your history
- **Compliance checks** — flagged automatically against Australian real-estate guidelines
- **Full UI/UX redesign** — modern sidebar layout, polished components, responsive design

---

## Quick start

```bash
pip install -r requirements.txt

# Ollama needs to be installed separately (only required for LLaVA descriptions):
#   https://ollama.ai
#   ollama pull llava

python app.py
```

Open `http://localhost:5000` — you'll be redirected to the login page.

### Default credentials

| Role  | Username | Password   |
|-------|----------|------------|
| Admin | `admin`  | `admin123` |
| Agent | `agent`  | `agent123` |

> **⚠️ Change these immediately in production** — the admin can update or remove these accounts from the Users page.

---

## What's where

```
Estate_AI/
├── app.py                       # Flask entry point
├── auth/
│   ├── database.py              # SQLite schema + helpers
│   ├── routes.py                # /api/auth/* (login, register, logout, me)
│   └── admin_routes.py          # /api/admin/* (admin-only endpoints)
├── chat_ui/
│   ├── auth/                    # Login & registration pages
│   │   ├── login.html
│   │   ├── admin-login.html
│   │   ├── register.html
│   │   └── auth.css
│   ├── admin/                   # Admin console
│   │   ├── index.html
│   │   └── admin.js
│   ├── index.html               # Agent dashboard
│   ├── script.js
│   ├── style.css
│   └── translations.js          # 4 languages (EN, HI, ZH, JA)
├── models/                      # Existing AI pipeline (unchanged)
│   ├── yolo_model/
│   ├── clip_model/
│   └── llava_model/
├── data/                        # SQLite DB lives here (auto-created)
│   └── estate_ai.db
└── uploads/                     # User-uploaded property images
```

---

## URL routes

| URL                | What it shows                              |
|--------------------|--------------------------------------------|
| `/`                | Redirects to `/login` or the right portal  |
| `/login`           | Agent sign-in                              |
| `/register`        | New agent registration                     |
| `/admin-login`     | Admin sign-in                              |
| `/app/`            | Agent dashboard (auth required)            |
| `/admin/`          | Admin console (admin role required)        |

---

## Configuration

### Environment variables

```bash
export SECRET_KEY="your-random-secret-here"   # Used for session signing
```

If not set, a development default is used. **Always set this in production.**

### Database

A SQLite database at `data/estate_ai.db` is created automatically on first run. To reset everything (fresh demo state), simply delete this file — defaults will be re-seeded on next start.

### Compliance rules

Five default Australian real-estate guidelines are seeded on first run:

1. No price baiting (`"starting from"`, `"from only"`)
2. No guaranteed returns
3. Avoid superlatives without proof
4. No discriminatory language
5. Avoid unsubstantiated absolute claims

Admins can add, edit, or disable these from the **Compliance** page in the admin console. Each rule is a Python regex pattern with a severity (`warning` | `error`) and a message shown to the agent.

---

## Notes on the AI pipeline

The original AI pipeline is unchanged:

- **YOLOv8** detects objects in each photo
- **CLIP** classifies room types and identifies floor plans
- **LLaVA** (via Ollama) generates room descriptions and 5-dimension property analysis
- The text-template engine in `models/yolo_model/description.py` produces the final listing and FB/IG ads

The `/upload` endpoint now requires authentication and additionally:
- Saves every generation to the database
- Runs compliance checks on the listing text
- Returns `compliance` violations and `generation_id` in the response

Templates managed via the admin console are returned by `GET /api/templates` — they are reference-only in this build (the listing engine still uses its built-in templates), but the data layer is in place if you want to wire them into `description.py`.

---

## Troubleshooting

**"Cannot reach server"** — confirm Flask is running on port 5000 and that your browser is going to `http://localhost:5000` (not file://).

**LLaVA descriptions are empty** — Ollama isn't running or the `llava` model isn't pulled. The app will still produce a fallback description from CLIP+YOLO output.

**Lost the admin password** — delete `data/estate_ai.db` and restart. The admin/admin123 default will be re-seeded.

**Sessions feel weird** — clear cookies for `localhost:5000` and sign in again. The session cookie is `estate_token` and lasts 7 days.
