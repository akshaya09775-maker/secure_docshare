# Secure DocShare
### Secure Browser and Permission-Based Document Sharing System (with Time-Limited Access)

**Status: internal pilot / security-focused prototype** — see [Section 4](#4-enterprise--company-suitability) for what's production-ready today and what a real corporate deployment would still need.

A college-project-ready implementation combining two security modules into one Flask app:

1. **Secure Browser** — authenticated URL access with blocklist validation and browsing history.
2. **Secure Document Sharing** — encrypted document storage with permission-based, time-limited share links.

---

## 1. System Architecture

```
                         ┌─────────────────────────┐
                         │        Browser           │
                         │  (HTML/CSS/JS templates) │
                         └────────────┬─────────────┘
                                      │ HTTPS
                         ┌────────────▼─────────────┐
                         │      Flask Application     │
                         │  ┌──────────────────────┐  │
                         │  │  Auth (Flask-Login)   │  │
                         │  ├──────────────────────┤  │
                         │  │  Document Module      │  │
                         │  │  - Upload (encrypt)   │  │
                         │  │  - Share (token+TTL)  │  │
                         │  │  - Access gate        │  │
                         │  ├──────────────────────┤  │
                         │  │  Secure Browser Module│  │
                         │  │  - URL validation      │  │
                         │  │  - Blocklist check     │  │
                         │  └──────────────────────┘  │
                         └────────────┬─────────────┘
                                      │
                     ┌────────────────┼────────────────┐
                     │                                  │
           ┌─────────▼─────────┐            ┌───────────▼───────────┐
           │   Database (SQL)    │            │  Encrypted File Store  │
           │  users, documents,  │            │  (local /uploads dir,  │
           │  shares, logs, etc. │            │  Fernet/AES encrypted) │
           └─────────────────────┘            └────────────────────────┘
```

**Key security principle:** the raw file is never exposed by a static URL. Every
view/download request re-checks, server-side: identity, permission, expiry,
and revocation — every single time, not just once when the link is generated.

---

## 2. Modules

### A. Secure Browser
- Login required before use.
- URL normalization + validation: scheme check (http/https only), raw-IP block, domain blocklist (exact + subdomain match).
- Every attempt (allowed or blocked) is written to `browsing_history` for audit.
- Opens validated links in a new tab (most sites block iframe embedding via `X-Frame-Options`, so a real embedded "safe frame" isn't feasible for arbitrary third-party sites — worth mentioning in your viva as a known constraint, not a bug).

### B. Secure Document Sharing
- Registration/login with hashed passwords (`werkzeug.security`, PBKDF2-SHA256).
- Upload → file encrypted with Fernet (AES-128-CBC + HMAC) before touching disk.
- Share → owner picks recipient (must be a registered user), permission (`view` or `download`), and expiry (10 min / 30 min / 1 hr / 1 day / custom).
- Each share gets a unique unguessable token (`secrets.token_urlsafe(32)`) — the link itself carries no meaningful data, all state lives server-side in the `shares` table.
- Access gate (`/shared/<token>`) checks, in order: token exists → viewer is logged in as the intended recipient → not revoked → not expired → then serves the page and logs the access.
- Owner can revoke a link immediately, independent of its original expiry.
- Full audit trail in `access_logs`: who, what action, from what IP, when.

---

## 3. Database Schema

| Table | Purpose | Key columns |
|---|---|---|
| `users` | Registered accounts | id, username, email, password_hash, created_at |
| `documents` | Uploaded files (encrypted on disk) | id, owner_id, original_filename, stored_filename, file_size, uploaded_at |
| `shares` | One row per share link | id, document_id, shared_by_id, shared_with_id, token, permission, expires_at, revoked, created_at |
| `access_logs` | Audit trail of shared-link access | id, share_id, user_id, action, ip_address, timestamp |
| `browsing_history` | Secure browser activity log | id, user_id, url, status, reason, timestamp |
| `blocked_domains` | Domain blocklist for the browser module | id, domain |

All tables are defined in `models.py` using SQLAlchemy ORM, so the same code
works against SQLite (default, zero-config) or MySQL (see setup below).

---

## 4. Enterprise / Company Suitability

**Current status: a strong security-focused prototype, suitable for an internal pilot — not yet a production-ready enterprise deployment.**

The architecture demonstrates the right *shape* of a secure document-sharing system: server-side enforcement on every access, encryption at rest, unguessable tokens, and full audit logging. That foundation is sound and worth building on. What it doesn't yet have is the operational hardening a real company rollout requires — those gaps are itemized below so they're explicit rather than discovered later.

**Good fit for, today:**
- An internal pilot with a small, trusted user group (e.g. one team sharing internal documents).
- A reference implementation for evaluating the access-control and audit-logging design before investing in a production build.
- A base to layer enterprise controls onto, rather than a rewrite from scratch.

**Not yet appropriate for:**
- Handling regulated data (PII, financial records, health records) or anything subject to compliance regimes (SOC 2, ISO 27001, HIPAA, GDPR) without the additions below.
- External/customer-facing deployment, or any deployment outside a controlled internal network.
- Unsupervised production use without a security review.

### Remaining enterprise security requirements before real corporate deployment

| Area | Gap today | What's needed |
|---|---|---|
| **Identity** | Local username/password only | SSO/SAML or OIDC integration with the company's identity provider; enforced MFA |
| **Secrets & key management** | `FERNET_KEY` set via a plain environment variable | A managed secrets store (e.g. AWS Secrets Manager, HashiCorp Vault, Azure Key Vault) with key rotation and no key material in `.env` files or shell history |
| **Rate limiting & abuse prevention** | None on login, register, or share endpoints | Flask-Limiter (or a gateway-level equivalent) on auth and share-creation endpoints to stop brute-force and enumeration attempts |
| **Network exposure** | Runs as a bare Flask dev server | A production WSGI server (gunicorn/uWSGI) behind TLS termination, a reverse proxy, and ideally a WAF |
| **File handling** | No malware/virus scanning on upload | Antivirus/malware scanning (e.g. ClamAV) integrated into the upload pipeline before a file is stored |
| **View-only enforcement** | View-only files can still be downloaded via browser dev tools or a screenshot | Server-side rendering to watermarked images or a locked-down PDF.js viewer for true view-only protection |
| **Logging & monitoring** | Access logs live only in the app database | Centralized logging/SIEM integration, alerting on anomalous access patterns, and log retention policy |
| **Backup & recovery** | No backup strategy defined | Automated, encrypted backups of the database and file store, with a tested restore/DR plan |
| **Access control granularity** | Two permission levels (view/download), no org structure | Role-based access control (RBAC), groups/teams, and admin-level oversight of all shares |
| **Compliance & governance** | Not mapped to any framework | Formal mapping to relevant frameworks (SOC 2, ISO 27001, or industry-specific requirements) plus a data retention/deletion policy |
| **Testing** | No security testing performed beyond manual review | Third-party penetration testing and a dependency vulnerability scan (e.g. `pip-audit`) before go-live |
| **Email/notifications** | None — recipients must be told a link exists out-of-band | Email or in-app notifications on share creation, expiry, and access, ideally with OTP verification on registration |

None of this is a knock on the current implementation — it's the standard checklist between "a well-built prototype" and "something a company's security team signs off on." Treat this table as the pilot's roadmap, not a list of flaws to apologize for.

---

## 5. Setup Instructions

### Quick start (SQLite, no extra setup)
```bash
cd secure_docshare
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Visit **http://127.0.0.1:5000**, register two accounts (e.g. Alice and Bob) so
you can demo sharing between them.

### Switching to MySQL
1. `pip install pymysql` (already in requirements.txt).
2. Create the database:
   ```sql
   CREATE DATABASE secure_docshare;
   ```
3. Set the environment variable before running:
   ```bash
   export DATABASE_URL="mysql+pymysql://root:yourpassword@localhost/secure_docshare"
   python app.py
   ```

### Generating your own encryption key (recommended for any real deployment)
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
export FERNET_KEY="paste-the-generated-key-here"
```

---

## 6. Demo Script (for viva)

1. Register **Alice** and **Bob**.
2. Log in as Alice → Upload `project.pdf`.
3. Share it with Bob: permission = Download, expiry = 1 minute (use "Custom" → `1`).
4. Log out, log in as Bob → Dashboard → "Shared With Me" → Open the link. Show it works, show the live countdown.
5. Wait 60+ seconds, refresh the same link → show the **"This document-sharing link has expired"** page.
6. Log back in as Alice → History & Logs → show the access log entry for Bob's view.
7. Repeat sharing but this time click **Revoke** immediately as Alice → show Bob is denied instantly, before expiry.
8. Switch to the **Secure Browser** tab → try a normal URL (allowed) and one of the seeded blocklist domains, e.g. `malicious-test.com` (blocked) → show both appear in History.

---

## 7. Security Notes (what to highlight in your report)

- **Passwords** are never stored in plaintext — hashed with PBKDF2 via Werkzeug.
- **Files** are encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256 for integrity), so raw files on disk are unreadable without the app's key.
- **Access control is enforced server-side on every request**, not just at link-generation time — this is what actually makes the time limit unbypassable, rather than relying on a client-trusted expiry.
- **Token design**: the share token is a random 32-byte URL-safe string, not a predictable ID — it can't be guessed or enumerated.
- **Revocation is independent of expiry**: state is stored in the database (`revoked` flag), not just encoded in the link, so access can be killed early.
- **Full audit logging** for both modules supports traceability — a real requirement in most "secure sharing" systems.

### Known limitations (good to mention proactively in a viva — shows understanding, not weakness)
- View-only documents are still downloadable via browser dev tools/screenshot — true DRM-grade view-only protection needs server-side rendering to images/watermarked PDF.js, which is a good "future work" extension to mention.
- No email/OTP verification on registration in this version — could be added with Flask-Mail.
- No rate-limiting on login/share endpoints in this base version — Flask-Limiter would be the natural addition.
- The custom Fernet key ships with a default value for demo convenience — must be replaced via `FERNET_KEY` env var for any non-classroom deployment.

---

## 8. Project Structure

The app is split into **Flask Blueprints** — one file per module/page group,
each registered onto the main app in `app.py`. This keeps routes organized
and makes it easy to explain "this file = this feature" in a viva.

```
secure_docshare/
├── app.py                    # Application factory: config, db, registers all blueprints
├── config.py                 # Configuration (DB, upload, encryption, blocklist)
├── extensions.py             # Flask-SQLAlchemy / Flask-Login instances
├── models.py                 # Database schema (6 tables)
├── requirements.txt
│
├── blueprints/                # One file per feature/page group
│   ├── auth.py                # /register  /login  /logout
│   ├── main.py                 # /  /dashboard
│   ├── documents.py            # /upload  /share/<id>  /shared/<token>  /revoke/<id>
│   └── browser.py              # /browser  /history
│
├── utils/
│   ├── encryption.py          # Fernet encrypt/decrypt helpers
│   ├── validators.py          # Secure browser URL validation
│   └── helpers.py             # Shared helpers (e.g. client_ip)
│
├── templates/                  # Jinja2 HTML templates (one per page)
├── static/style.css
└── uploads/                    # Encrypted file storage (created at runtime)
```

### How endpoints map to blueprints
Each blueprint's routes are referenced with a `blueprint_name.function_name`
prefix in `url_for()` — e.g. the login page is `auth.login`, the dashboard is
`main.dashboard`, viewing a shared file is `documents.view_shared`. This is
standard Flask practice once an app grows past a handful of routes, and it's
what lets `blueprints/documents.py` be read and understood on its own,
without needing the rest of the app open at the same time.
