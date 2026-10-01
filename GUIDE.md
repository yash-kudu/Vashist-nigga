# NutriHealth — Build Guide & Viva Walkthrough

A step-by-step account of how this project is put together, written so
you can explain every part of it in your own words during evaluation.

---

## 1. Project Directory Structure

```
nutrihealth/
├── app.py                  # Flask app: routes, auth, database logic
├── schema.sql               # SQL table definitions
├── requirements.txt          # Python dependencies (just Flask)
├── nutrition.db              # SQLite database file (created on first run)
├── templates/                 # Jinja2 HTML templates (server-rendered)
│   ├── base.html               # Shared layout: header, nav, footer
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html          # wellness score, hydration, activity, quick-add
│   ├── log_food.html
│   ├── food_history.html
│   ├── health_metrics.html
│   ├── community.html          # feed, posting, active challenges
│   └── profile.html
└── static/
    ├── css/
    │   └── style.css           # Hand-written CSS, no frameworks
    └── js/
        └── script.js           # Vanilla JS: validation + small UI touches
```

**Why this layout?** Flask expects HTML files in a folder called
`templates/` and anything served as-is (CSS, JS, images) in a folder
called `static/`. This is Flask's own convention, not something we
invented — it's why `render_template()` and `url_for('static', ...)`
work without extra configuration.

**Since this walkthrough was first written**, three things were added
on top of the same structure (no new files or folders): a rule-based
chat assistant (`FOOD_DB`, `build_chat_reply()`, and the routes
`/api/chat` + `/api/foods/search` in `app.py`), a live food-search box
on the Log Food page, and small load-in animations on the dashboard's
rings and bars. See sections 8 and 9 below.

---

## 2. Environment & Database Setup

### Installing Flask

```bash
pip install flask
# or, using the requirements file:
pip install -r requirements.txt
```

### Running the app

```bash
python app.py
```

You should see:

```
NutriHealth running at http://127.0.0.1:5000
```

Open that address in a browser. The first time you run it, `init_db()`
executes `schema.sql` against `nutrition.db`, creating three tables.
On every later run, the same `CREATE TABLE IF NOT EXISTS` statements
just do nothing, since the tables already exist — so it's always safe
to start the app.

### Database tables (from `schema.sql`)

**`users`** — one row per registered person.
| column | purpose |
|---|---|
| id | primary key |
| username, email | unique login identifiers |
| password_hash | a *hashed* password, never the real one |
| calorie_goal | the user's daily target, editable in Profile |

**`food_logs`** — one row per meal a user logs.
| column | purpose |
|---|---|
| user_id | which account this entry belongs to |
| food_name, meal_type, calories, protein, carbs, fats | the meal data |
| log_date | which day this entry counts toward |

**`health_metrics`** — one row per weight/height check-in.
| column | purpose |
|---|---|
| user_id, weight_kg, height_cm, bmi, log_date | self-explanatory |

**`daily_logs`** — one row per user *per day*, holding that day's
hydration and step counts.
| column | purpose |
|---|---|
| user_id, log_date | together, uniquely identify one day for one user |
| water_glasses, steps | updated in place by the +1/-1 and +500/+1000 buttons |

This table has a `UNIQUE(user_id, log_date)` constraint, so instead of
inserting a new row every time someone adds a glass of water, the app
looks up (or creates) today's single row and updates the number in
place — that's what `get_or_create_daily_log()` in `app.py` does.

**`community_posts`** — the one table that is *not* filtered by the
current user when displayed. Every user can see every post; `user_id`
is kept so we know who posted it (shown as `author`), but the feed
query has no `WHERE user_id = ?` clause on purpose.

Every table that stores personal data has a `user_id` foreign key
back to `users`. This single design choice is what makes the app
multi-user: every query is filtered by `WHERE user_id = ?`, so one
person never sees another person's meals or metrics.

---

## 3. Authentication (Session-Based)

This app does **not** use any login library — it's built from Flask's
own `session` object plus `werkzeug.security`, both of which ship
with Flask.

**Registration (`/register`)**
1. The form posts `username`, `email`, `password`, `confirm_password`.
2. The server checks all fields are filled, the password is at least
   6 characters, and both password fields match.
3. It checks the database for an existing username/email.
4. If everything passes, `generate_password_hash(password)` turns the
   password into a salted hash (e.g.
   `pbkdf2:sha256:600000$...$...`) — this is what actually gets
   stored, never the plain password.

**Login (`/login`)**
1. Look up the user row by username.
2. `check_password_hash(stored_hash, submitted_password)` re-hashes
   the submitted password with the same algorithm and salt, and
   compares the result. This is the only correct way to check a
   password against a hash — you can't "decrypt" a hash back to the
   original.
3. On success, `session["user_id"]` and `session["username"]` are
   set. Flask signs this session data with `app.secret_key` and
   stores it in a cookie, so the browser proves who's logged in on
   every later request without sending the password again.

**Protecting pages**
Every page that needs a logged-in user (dashboard, log food, etc.)
is wrapped with a custom decorator:

```python
def login_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_function(*args, **kwargs)
    return wrapped_view
```

Put `@login_required` above any route function and it will bounce
anonymous visitors to the login page automatically.

**Logout (`/logout`)**
`session.clear()` wipes the session cookie's contents server-side,
so the browser can no longer prove it's logged in.

---

## 4. Handcrafted UI (No Frameworks)

**CSS** (`static/css/style.css`) is written by hand, with no
Bootstrap or Tailwind. All colors, spacing, and radii are defined
once at the top as CSS custom properties (`:root { --color-primary: ... }`),
so the whole visual theme can be changed by editing a handful of
lines. Layout uses plain CSS Grid and Flexbox — no grid framework
needed.

**JavaScript** (`static/js/script.js`) is plain vanilla JS with zero
dependencies. It's responsible only for things a browser needs
*before* the page is submitted to the server:

- Toggling the mobile navigation menu open/closed.
- Checking that the two password fields match while the user types
  (register page), so they get feedback before hitting submit.
- Estimating calories live from protein/carb/fat entries using the
  standard Atwater factors (4 kcal/g protein, 4 kcal/g carbs,
  9 kcal/g fat), shown as a hint under the food form.
- Previewing BMI instantly as weight/height are typed, before the
  form is even submitted.
- Fading out flash messages automatically after a few seconds.

**Important distinction for your viva:** all of this JavaScript is
*convenience only*. Every value it checks is checked again on the
server in `app.py`, because a user can always disable JavaScript or
send a request directly (with `curl`, for example) — the server can
never trust the browser alone.

---

## 5. The Dashboard

The `/dashboard` route in `app.py` does three things before handing
data to the template:

1. **Fetches today's food logs** for the logged-in user
   (`WHERE user_id = ? AND log_date = ?`).
2. **Sums calories and macros** with plain Python `sum()` over the
   rows — no special library needed for this.
3. **Computes percentages** for the macro breakdown bars:
   ```python
   protein_pct = round((total_protein / macro_gram_total) * 100)
   ```
4. **Computes calorie progress** against the user's goal, used to
   drive a CSS `conic-gradient` ring (no chart library — it's a
   circle whose colored arc length is set by a CSS variable, `--pct`,
   passed in from the template).

The template (`dashboard.html`) then just displays these
already-calculated numbers — templates in this project never do
calculations themselves, which keeps the "business logic" in one
place (`app.py`) and the "presentation" in another (`templates/`).

---

## 6. How It Works — Routing & Data Flow (Viva Summary)

Use this as your one-paragraph answer if asked "walk me through what
happens when a user logs a meal":

> When the browser requests a page, Flask matches the URL to a
> Python function using `@app.route(...)`. For `/log-food`, a `GET`
> request just renders the empty form (`render_template("log_food.html")`).
> When the form is submitted, it's a `POST` to the same URL. Flask
> reads the submitted fields with `request.form.get(...)`, validates
> them in Python, and if they're valid, runs an `INSERT INTO food_logs`
> SQL statement tagged with the current user's `user_id` from the
> session. It then commits the change and redirects the browser to
> `/dashboard`, which re-queries the database and shows the updated
> totals. Nothing is stored in the browser itself — every value lives
> in `nutrition.db` on the server, which is why the data is still
> there if you log out, close the browser, and log back in later, or
> log in from a different device.

**Request/response cycle, in order:**

```
Browser (form submit)
   │  POST /log-food  (username/email/password never sent again —
   │                    the session cookie proves identity)
   ▼
Flask route function (app.py)
   │  1. request.form.get(...) reads the submitted values
   │  2. Python validates them
   │  3. sqlite3 INSERT ... VALUES (?, ?, ...) writes to nutrition.db
   ▼
redirect(url_for("dashboard"))
   ▼
Flask route function (app.py)
   │  1. SELECT ... FROM food_logs WHERE user_id = ? AND log_date = ?
   │  2. Python sums/calculates totals
   ▼
render_template("dashboard.html", total_calories=..., ...)
   ▼
Browser receives complete HTML, already showing the new totals
```

**Why every SQL query uses `?` placeholders instead of inserting
values directly into the string:** this is *parameterized SQL*, which
prevents SQL injection — a common security question in viva. Writing
`f"SELECT * FROM users WHERE username = '{username}'"` would let
someone type a username like `' OR '1'='1` and bypass the check
entirely. Using `db.execute("... WHERE username = ?", (username,))`
makes that impossible, because the value is never interpreted as SQL
syntax.

---

## 7. Wellness Score, Hydration, Activity, and Community

**Calculated Wellness Score** (`calculate_wellness_score()` in
`app.py`) is a simple 0–100 number blending three habits computed
fresh on every dashboard load — nothing is stored:
- up to 40 points for how close today's calories are to the user's
  goal (both under- and over-eating reduce this)
- up to 30 points for hydration progress toward 8 glasses
- up to 30 points for step progress toward 10,000

It's intentionally simple and worth describing as "a teaching-friendly
formula, not a clinical metric" if asked in viva — real wellness
scoring products use far more inputs and peer-reviewed weighting.

**Hydration Tracker** and **Daily Activity** both work the same way:
a small form with a hidden `<input type="hidden">` posts an action
(`add`/`remove` for water, an `amount` for steps) to a route that
updates today's single `daily_logs` row and redirects back. No
JavaScript is required for either to function — they're plain HTML
forms, consistent with the rest of the app's traditional pattern.

**Quick-Add Verified Foods** is a hardcoded Python list
(`QUICK_ADD_FOODS` in `app.py`) of common foods with pre-filled
nutrition values. Each button is its own tiny form carrying only a
`food_key`; the actual calorie/macro numbers are looked up
server-side from that list, not trusted from the request. This
matters for a viva security question: if the numbers were sent from
the browser instead, someone could edit the page's HTML and log a
cookie as "0 calories."

**Interactive Community** (`community.html`) is the one part of the
app that intentionally ignores the "each user only sees their own
data" rule — `SELECT * FROM community_posts` has no `WHERE user_id`
filter, because the feed is meant to be shared. The **Active
Challenges** panel, on the other hand, is *not* a separate
to-do-list feature — its progress bars just re-read the same
`daily_logs` and `food_logs` rows already being used everywhere else.
That's what the **Auto-Sync** label means: there's no "mark complete"
button, because logging a glass of water or a meal automatically
moves the matching challenge forward.

---

## 8. Ragbot — the Rule-Based Chat Assistant

There's a chat bubble in the corner of every page (`base.html`,
`.chatbot-widget`). It looks like an AI chatbot, but it is **not**
calling any external AI service — no OpenAI, no Claude API, nothing.
Everything it says is built from plain Python `if`/`regex` pattern
matching plus your own rows in the database. This distinction is
worth stating clearly in a viva: it's "retrieval, not generation" —
it *retrieves* facts from `FOOD_DB` and your logged data, and slots
them into a pre-written sentence. It can never say anything outside
those sentences.

**How a message gets a reply (`build_chat_reply()` in `app.py`):**
1. The message is lower-cased and checked against a series of regex
   patterns, in order, like a decision tree:
   - Is it just a greeting ("hi", "hello")? → canned welcome reply.
   - Does it contain "help"? → list of things it can do.
   - Does it mention "water", "steps", "wellness", "calories left",
     or "bmi"? → look the real number up in the database and answer
     with it (this reuses `compute_dashboard_stats()`, the same
     function the dashboard itself calls).
   - Otherwise, scan the text for any food name from `FOOD_DB`
     (`find_food_mentions()`).
2. **Finding foods in free text:** `find_food_mentions()` checks the
   message for every keyword in `FOOD_DB` (longest keywords first, so
   "greek yogurt" matches before plain "yogurt"), and for each hit,
   looks at the word right before it to catch a quantity — a digit
   ("3 rotis") or a number word ("a banana", "two eggs" via a small
   `NUMBER_WORDS` dictionary).
3. If the message reads like a question ("calories in a mango?")
   it just reports the numbers back without logging anything.
   Otherwise, it inserts a real row into `food_logs` for each food
   found — the exact same `INSERT` pattern the Quick-Add buttons use
   (pulled into a shared helper, `insert_food_log()`, so both features
   can't drift out of sync with each other).
4. The route `POST /api/chat` receives `{"message": "..."}` as JSON
   and returns `{"reply": "...", "logged": true/false}`.

**On the frontend**, `script.js` intercepts the chat form's submit,
sends that JSON with `fetch()`, and drops the bubble into the chat
window — no page reload needed for the conversation itself. If
`logged` comes back `true`, the page silently reloads a second and a
half later so the dashboard's numbers/rings/bars catch up.

**Live food search** on the Log Food page (`GET /api/foods/search?q=`)
works the same idea in reverse: as you type, JavaScript asks the
server "what foods match this text?", the server checks `FOOD_DB` and
returns JSON, and JavaScript renders each match as a clickable
suggestion that auto-fills the calories/protein/carbs/fats fields —
so `FOOD_DB` now powers three features (Quick-Add, this search box,
and the chatbot) from one single list, instead of three separate
copies of the same data.

---

## 9. Making the UI Feel More Dynamic

Two techniques, both CSS/JS-only — no backend changes needed:

**Animated rings and bars.** The calorie ring, wellness ring, macro
bars, hydration glasses, and steps bar are all rendered by Jinja with
their *final* value already baked in (e.g. `style="--pct: 72;"`).
On page load, `script.js` reads that target value back out, resets it
to `0`, forces the browser to notice (`void el.offsetWidth`), then
sets it back to the real value on the next animation frame. Because
the CSS now has a `transition` on that property, the browser animates
smoothly from 0 up to the real number instead of just appearing
instantly. The rings needed one extra trick: browsers don't normally
know how to animate a custom property like `--pct`, so it's declared
with `@property --pct { syntax: '<number>'; ... }` in `style.css`,
which tells the browser "treat this as a number you can transition,"
not just as text.

**Count-up numbers.** The big numbers (calories, steps, wellness
score) use a small `requestAnimationFrame` loop that counts from 0 up
to the target over about 900ms, rounding as it goes — the same trick
behind most "animated stat counter" effects you see on websites.

---

## 10. Suggested Talking Points for Evaluation

- **Why Flask + SQLite and not a bigger framework?** SQLite needs no
  separate server process — it's a single file (`nutrition.db`) —
  which makes the whole project runnable on any machine with just
  Python installed. Flask is a "micro-framework": it gives you
  routing and templating and lets you write everything else yourself,
  which is why the code stays readable for a course project.
- **Why session-based auth instead of a login library?** To
  demonstrate understanding of how authentication actually works
  underneath — signed cookies, password hashing, and server-side
  session state — rather than treating it as a black box.
- **Where does the "multi-user" requirement show up in the code?**
  Every table with personal data has a `user_id` column, and every
  query that touches it is filtered by `session["user_id"]`. This is
  the core pattern behind almost all real multi-user web apps.
- **Is the chatbot "real AI"?** No, and saying so clearly is a good
  answer, not a weakness — it's a deliberate design choice to keep the
  whole app self-contained, offline-capable, and free to run, using
  the same regex-and-database techniques the rest of the app already
  relies on, rather than depending on a paid external API.
- **What would you add with more time?** Password-reset via email,
  input length limits, pagination on food history for very active
  users, CSRF tokens on forms (Flask-WTF adds this in a few lines),
  and — for the chatbot specifically — swapping the rule-based matcher
  for a real language-model API if broader free-text understanding
  were needed.
