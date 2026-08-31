# Plan: Build the Regular User Experience

## Goal
Give the **User** role a proper set of pages, matching the existing sidebar/Tailwind design:
1. **User Dashboard** — landing page after login.
2. **My Data** — shows personal data linked to the logged-in user.
3. **Submit DSR** — submit one of the standard 6 rights (with optional proof-of-identity upload), view own DSR + status.
4. **Privacy Notices** — read published notices.
5. **Consent Management** — consumer-friendly opt-in/opt-out toggles.
6. **My Profile** — exists; keep as-is.

## Decisions (confirmed with user)
- Scope: Regular User experience only.
- Pages: Dashboard, View My Data, Submit DSR, View Privacy Notices (all four).
- Design: same layout as Admin/DPO (dark sidebar, Tailwind).
- "My Data": **link data to users** — add `user_id` to `personal_data_inventory` so each user sees only their own rows.
- DSR types: standard 6 rights (Access, Rectification, Erasure, Restriction, Portability, Objection).
- **DSR proof upload:** DSR submission form includes a simple file-upload field for "Proof of Identity / Authorization" to satisfy the authorized-representative/legal-heir edge case without complex verification logic. Stored server-side; not validated for content.
- **Consent UX:** User-facing consent page uses modern **Opt-In / Opt-Out** toggles, not the DPO's "Active/Revoked" dropdowns.

---

## Part A — Backend (`app.py` + schema)

### A1. Schema changes
**`personal_data_inventory`** — add `user_id INTEGER` column (nullable, FK → users.id).
**`dsr_requests`** — add `proof_document TEXT NULL` column to store the uploaded filename/path.

Update `init_db.py` schema accordingly. Update the DSR insert in `app.py` to accept the optional proof field.

### A2. New / modified routes (all `@login_required()`):
| Route | Method | Purpose |
|---|---|---|
| `/api/my-data` | GET | Inventory rows where `user_id = session['user_id']` |
| `/api/dsr/my` | GET | DSR requests for the logged-in user (id, type, status, submitted_at, notes, has_proof) |
| `/api/dsr/submit` | POST | Create a DSR for the logged-in user. Validates type is one of the 6 rights. Accepts optional file upload (multipart form) saved to `instance/uploads/`, stores filename in `dsr_requests.proof_document`. |
| `/api/public-privacy-notices` | GET | Published notices only (`is_published = 1`), for Users |
| `/api/user-dashboard` | GET | Returns consent summary + open DSR count for the logged-in user |

- Existing `/api/dashboard-stats` is Admin/DPO-only and stays that way.
- Role guard on new routes: any logged-in user; they only touch their own rows via `session['user_id']`.
- **File upload handling:** `request.files.get('proof')`; if present and `filename != ''`, secure the filename, save to `instance/uploads/` (created on startup), store `proof_document = filename`. Size/type limits: cap at 5MB, allow common types (pdf, png, jpg, jpeg, webp). Reject oversized/invalid type with a 400. This is storage-only; no content verification (per requirement).

### A3. Seed a regular User
- Add to `init_db.py`: `user@example.com` / `user` with role `User`, plus:
  - 2-3 linked `personal_data_inventory` rows for them.
  - 1 Pending DSR so their dashboard/DSR pages have content.
- Run `init_db.py` once (resets DB — acceptable dev data).

---

## Part B — Frontend (`templates/index.html`)

### B1. Sidebar for the `User` role
Current: `['link-my-consents', 'link-user-profile']`.
New: `['link-user-dashboard', 'link-my-data', 'link-dsr-requests', 'link-privacy-notices', 'link-my-consents', 'link-user-profile']`.
- `link-dsr-requests` and `link-privacy-notices` are shared IDs with DPO/Admin; branch loaders by `userRole === 'User'`.

### B2. New / modified loader functions:
- `loadUserDashboard()` → `/api/user-dashboard`; consent summary cards + recent own DSRs.
- `loadMyData()` → `/api/my-data`; table of the user's data items (category, location, purpose).
- `loadDsrRequests()` → branch for User: call `/api/dsr/my`, render submit form + status list. Form = dropdown of 6 rights + optional file input + submit → POST multipart to `/api/dsr/submit`, reload on success.
- `loadPrivacyNotices()` → branch for User: call `/api/public-privacy-notices`, read-only list (no Edit/Publish).
- **`loadMyConsents()`** → for User role, render **toggle switches** (Opt-In / Opt-Out) instead of the `Active`/`Revoked` `<select>`. The backend endpoint `/consents/update/<id>` already accepts `status=Active|Revoked`, so map toggle → `Active`/`Revoked` on change. Add a `data-action="toggle-consent"` handler.

### B3. Default view on login
- User → `loadUserDashboard()` (was `loadMyConsents()`).

---

## Part C — Verification
1. Restart server; run `init_db.py` (applies schema + seed).
2. Log in as `user@example.com`/`user`:
   - Land on User Dashboard; confirm consents + open DSR count.
   - My Data shows only the user's linked rows.
   - DSR page: submit with and without a proof file → appears as Pending; verify file saved + filename stored in DB.
   - Privacy Notices: only published notices; no Edit/Publish buttons.
   - Consent Management: toggle switches work (Opt-In/Opt-Out) and persist; Profile still works.
3. Log in as Admin/DPO:
   - Dashboard + all management pages still work.
   - `/api/dashboard-stats` still returns full inventory.
   - DPO consent page still shows dropdowns (unchanged).
4. Clean up test submissions/files created during verification.

## Out of scope
- CSRF protection (separate task).
- Email editable on user edit (already decided locked).
- Content verification of uploaded proof files (intentionally out of scope per requirement).
- Deleting/viewing uploaded files by DPO (future).

---

# Risk Assessment (most → least risky)

## R1 — `init_db.py` drops all tables / wipes data (HIGH)
**Why risky:** Every run destroys the DB. We re-seed, but if the app has real data it's gone. Also if the re-seed has a bug, the app has no data to test against.
**Mitigation:**
- Only run once, explicitly, at the start of implementation. Do **not** run it as part of any "restart" loop.
- Back up the current `compliance_system.db` to `compliance_system.db.bak` before running.
- Make the seed script idempotent-ish (use `INSERT OR IGNORE` on users by email) so a re-run doesn't create duplicate admins.
- Verify the seeded users/logins immediately after the run before doing anything else.

## R2 — File upload handling (NEW, HIGH)
**Why risky:** First time the app handles file I/O. Errors here → 500s or broken submissions. Also: insecure filenames, path traversal, oversized files, wrong Content-Type.
**Mitigation:**
- Use `werkzeug.utils.secure_filename()`.
- Validate `content_length`/file size (cap 5MB) and allowlist extensions before saving.
- Save into `instance/uploads/` (create dir at startup with `os.makedirs(exist_ok=True)`), never use the client filename directly.
- Wrap the save in try/except; on any failure return a clear 400, never a 500.
- Test: upload a valid file, an oversized file (rejected), and a disallowed type (rejected); confirm no file left behind on rejection.

## R3 — Frontend consent toggle regression (MEDIUM-HIGH)
**Why risky:** `loadMyConsents()` is shared by User and DPO/Admin. Changing it for Users could break the DPO's table (which must stay dropdown + read-only). Both roles already use the same function.
**Mitigation:**
- Branch inside `loadMyConsents()` strictly on `userRole === 'User'`; DPO/Admin path untouched.
- Keep the existing `window.updateConsent()` function and reuse it from the toggle handler (map toggle value → `Active`/`Revoked`).
- Verify DPO's consent page looks/behaves identically after the change.

## R4 — Shared `link-dsr-requests` / `link-privacy-notices` IDs across roles (MEDIUM)
**Why risky:** Both DPO/Admin and User use these IDs, but the endpoint + rendering differ by role. Risk: User clicking a page gets the DPO version (or vice versa) if branching is missed.
**Mitigation:**
- Branch loaders by `userRole` at the top; never fall through to the other role's fetch.
- Use distinct element IDs for the User submit form (`user-dsr-form`) to avoid collisions.
- Test both roles' DSR + privacy pages after implementation.

## R5 — Adding `user_id` to inventory breaks Admin/DPO dashboard (MEDIUM)
**Why risky:** `/api/dashboard-stats` and `/api/personal-data-inventory` do `SELECT *` and return everything. If the schema change or a new filter accidentally applies to them, the admin dashboard could show partial data or error.
**Mitigation:**
- Do **not** change the existing admin endpoints — leave `SELECT *` untouched (all rows for DPO/Admin).
- Only the new `/api/my-data` filters by `user_id`.
- After schema change, confirm admin inventory still returns all rows.

## R6 — DSR submit / list scoping to the logged-in user (MEDIUM)
**Why risky:** If the `user_id` is taken from anywhere but `session['user_id']`, a user could see or create requests for other people.
**Mitigation:**
- Always derive `user_id` from `session['user_id']` in both `/api/dsr/my` and `/api/dsr/submit` — never from the form body.
- Confirm a user cannot fetch another user's DSRs (test with two user accounts if needed).

## R7 — `init_db.py` schema drift from the live DB (LOW-MEDIUM)
**Why risky:** The DB currently exists without `user_id` / `proof_document`. If `init_db.py` and `app.py` disagree, queries fail at runtime.
**Mitigation:**
- Update both `init_db.py` schema AND `app.py` queries in the same pass.
- Run a smoke test immediately after (login + each new endpoint) before building the UI.

## R8 — Styling/UX risk on the new pages (LOW)
**Why risky:** Consumer-friendly toggles and new pages could look off, but this is cosmetic and easy to iterate.
**Mitigation:**
- Reuse existing Tailwind classes/patterns from the current templates.
- Verify in the browser; low blast radius.

---

## Updated "Out of scope"
- CSRF protection (separate task).
- Email editable on user edit (already decided locked).
- Content verification of uploaded proof files (intentionally out of scope per requirement).
- Deleting/viewing uploaded files by DPO (future).
- Making DSR/notices pages richer than needed for the above.

## Updated "Risks / notes"
- `init_db.py` drops all tables — backed up first, run exactly once.
- Adding `user_id` to inventory: admin endpoints unchanged (`SELECT *`), no regression.
- Uploaded files are stored unverified (per requirement) — this is a deliberate, documented limitation.
