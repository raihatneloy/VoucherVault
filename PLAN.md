# VoucherVault Ireland — Live Balance Checking

**Fork:** https://github.com/raihatneloy/VoucherVault
**Branch:** `ie-vouchervault`
**Upstream:** https://github.com/l4rm4nd/VoucherVault
**Production:** `http://192.168.86.47:8000` → `https://vouchers.amarbari.net` (via Traefik + CF Tunnel)
**Development:** `docker-compose.dev.yml` (runserver auto-reload, volume-mounted source)

---

## Target Retailers

| Retailer | Method | Endpoint | Status |
|----------|--------|----------|--------|
| Lidl Ireland | JSON POST + Friendly Captcha | `lidl.ie/api/giftcards/balance` | ✅ Live |
| Dunnes Stores | JSON POST | `dunnesstores.com/api/giftcards/balance/` | 🟡 Planned |
| SuperValu | JSON POST | `supervalu.ie/api/giftcards/balance` | 🟡 Planned |
| Tesco Ireland | ASP.NET form | `tesco.ie/gift-cards/giftcardbalance/` | 🟡 Planned |
| Aldi Ireland | 3rd-party route | BIN-based detection | 🔴 Deferred |

---

## Architecture

```
User → vouchers.amarbari.net
  → Cloudflare (proxied DNS)
    → cloudflared tunnel (baps)
      → Traefik (baps-traefik, :80)
        → vouchervault container (:8000)
          → Django (uWSGI + Celery worker + Celery beat)
            → SQLite (/opt/app/database/db.sqlite3)
            → Redis (:6379, Celery broker)
            → balance-worker (:3001, Playwright captcha solver)
```

**Network topology:**
- `vouchervault` on `baps-oj-selfhost` network (Traefik auto-discovers via labels)
- `vouchervault` on `vouchervault_default` network (internal — redis, balance-worker)
- Traefik label: `Host(vouchers.amarbari.net)` → `vouchervault:8000`
- `baps.amarbari.net` still routes to BAPS backend via `PathPrefix(/)` — no conflict (Host rule has higher priority)

---

## Deployment

### Production (`docker-compose.yml`)
```bash
# Build & deploy
docker compose build
docker compose up -d

# Structure:
#   vouchervault           — uWSGI + Celery worker + Celery beat (bundled)
#   vouchervault-redis     — Redis broker
#   vouchervault-balance-worker — Playwright sidecar for captcha solving
```

### Development (`docker-compose.dev.yml`)
```bash
# First time
docker compose -f docker-compose.dev.yml build

# Daily work (no rebuild needed — source mounted as volumes)
docker compose -f docker-compose.dev.yml up -d

# Rebuild if deps change
docker compose -f docker-compose.dev.yml build --no-cache
```

**Dev differences from prod:**
- Uses `runserver` (auto-reload on file changes) instead of uWSGI
- Mounts `./myapp`, `./myproject`, `./locale`, `./manage.py` as volumes
- Celery worker + beat still run (via entrypoint.sh in background)
- Same balance-worker and redis as prod
- `DEBUG=True`, `PYTHONDONTWRITEBYTECODE=1`

**Prod image build (for release):** Use `docker-compose.yml` to build final image, deploy, and don't touch again until confident. Dev env uses volume mounts for iteration.

### Required Cloudflare config (one-time)
1. Add DNS `A` or `CNAME` record: `vouchers.amarbari.net` → proxied (orange cloud)
2. In Cloudflare Zero Trust → Access → Tunnels → `baps` tunnel:
   - Add public hostname: `vouchers.amarbari.net`
   - Service: `HTTP` → `localhost:80` (Traefik handles Host-based routing)

---

## Phase 0: Foundation ✅

- [x] **0.1 — Fork repo** → `raihatneloy/VoucherVault`
- [x] **0.2 — Set up remotes** → `origin` (SSH → fork), `upstream` (HTTPS → l4rm4nd)
- [x] **0.3 — Write implementation plan**
- [x] **0.4 — Create `ie-vouchervault` branch** for all our changes

---

## Phase 1: Data Model ✅

- [x] **1.1 — Add fields to `Item` model**
  - `balance_checker` (CharField: `lidl_ie`, `dunnes_ie`, `supervalu_ie`, `tesco_ie`)
  - `last_checked_balance` (DecimalField, nullable) — *legacy, replaced by live_balance*
  - `last_checked_at` (DateTimeField, nullable)
  - `live_balance` (DecimalField, nullable — canonical current balance)
- [x] **1.2 — Generate & run migration**
- [x] **1.3 — Update `ItemForm`** → add `balance_checker` dropdown to create/edit forms
- [ ] **1.4 — Update `UserPreference` model** (optional) → `auto_check_balance` toggle

---

## Phase 2: Balance Checker Engine ✅

- [x] **2.1 — Create `myapp/balance_checkers/` package**
  - `__init__.py`, `base.py` (abstract `BalanceChecker`), `providers/` directory
- [x] **2.2 — Implement `LidlIEProvider`**
  - POSTs to `lidl.ie/api/giftcards/balance` with `{cardNumber, pinNumber, country, locale, frcCaptchaToken}`
  - Friendly Captcha handled via external `balance-worker` (Playwright sidecar)
- [ ] **2.3 — Implement `DunnesIEProvider`**
- [ ] **2.4 — Implement `SuperValuIEProvider`**
- [ ] **2.5 — Implement `TescoIEProvider`**
- [x] **2.6 — Build `ProviderRegistry`**

### Balance Worker Sidecar (`balance-worker/`)

A separate Node.js service (Playwright-based) that solves Friendly Captcha and proxies balance requests:

- **API:** `POST /check` → `{cardNumber, pinNumber}` → `{success, balance, error}`
- Handles browser automation (headless Chromium)
- Runs on internal port 3001 (not exposed externally)
- Called by the Celery task in Django

---

## Phase 3: Async Balance Flow ✅

- [x] **3.1 — Celery task `check_item_balance`** (`myapp/tasks.py`)
  - Calls balance-worker sidecar for captcha solving
  - Updates `live_balance`, `last_checked_at` on Item model
  - Auto-sets `is_used = True` when `live_balance <= 0`
- [x] **3.2 — API endpoints**
  - `POST /api/check-balance/<uuid>/` → returns `{"task_id": "..."}` immediately
  - `GET /api/balance-status/<uuid>/` → returns task result (PENDING/SUCCESS/FAILURE)
- [x] **3.3 — Frontend polling**
  - "Check Balance" button triggers AJAX POST
  - Spinner + toast notification while checking
  - Polls every 3s for result
  - Success/failure toast with inline balance update
- [x] **3.4 — Session persistence**
  - Pending task IDs stored in Django session
  - On page refresh, checks for completed tasks and shows server-side banner
- [x] **3.5 — Live balance display**
  - Dashboard totals sum `live_balance` (not initial `value`)
  - Item detail shows "Loaded" (initial `value`) and "Live Balance" (`live_balance`)
  - Cards with `live_balance <= 0` auto-marked `is_used = True`
  - Fallback to `value` if never checked

---

## Phase 4: Traefik & Domain

- [x] **4.1 — Add Traefik labels** to `docker-compose.yml`
  - `Host(vouchers.amarbari.net)` → `vouchervault:8000`
  - Container connected to `baps-oj-selfhost` network
- [ ] **4.2 — Cloudflare DNS + Tunnel** (manual step in Cloudflare dashboard)
  - Add DNS record and public hostname in Zero Trust
- [ ] **4.3 — HTTPS with Let's Encrypt** (enable Traefik TLS certresolver)

---

## Phase 5: Remaining Retailers

- [ ] **5.1 — Implement `DunnesIEProvider`**
- [ ] **5.2 — Implement `SuperValuIEProvider`**
- [ ] **5.3 — Implement `TescoIEProvider`**
- [ ] **5.4 — Test with real gift cards** 🎯

---

## Phase 6: Polish & Edge Cases

- [ ] **6.1 — Inventory list view** → show live balance column with refresh icon per row
- [ ] **6.2 — Dashboard aggregate** → live balance totals in dashboard
- [ ] **6.3 — Rate limiting & caching** → don't re-check within 5 minutes
- [ ] **6.4 — Error messages** → user-friendly when balance check fails
- [ ] **6.5 — Handle card with no `pin`** (some retailers need PIN, some don't)
- [ ] **6.6 — Documentation update** (README, settings)

---

## Implementation Notes

### Lidl Ireland API (June 2026)

- **Balance check page**: `https://www.lidl.ie/c/gift-card-balance-check/s10073374`
- **API endpoint**: `POST https://www.lidl.ie/explore/giftyBalanceV2/gifty`
- **Payload**: `{cardNumber, pinNumber, country: "IE", locale: "en-IE", frcCaptchaToken: "..."}`
- **Friendly Captcha**: Required (sitekey `FCMGDDIJTON17UAD`). Solved via Playwright balance-worker sidecar.

### Code Architecture

- `balance_checkers/providers/lidl_ie.py` — Lidl API call logic
- `balance-worker/server.js` — Express server wrapping Playwright for captcha + balance check
- `myapp/tasks.py` — Celery task that orchestrates: Django → balance-worker → update DB
- `myapp/views.py` — `check_balance_async()` (triggers Celery), `balance_status()` (poll result)
- `templates/view-item.html` — "Check Balance" button, "Loaded" / "Live Balance" display

### Dev Workflow

1. Work on branch `ie-vouchervault`
2. Use `docker-compose.dev.yml` for iteration (no rebuild needed for code changes)
3. When confident, switch to `docker-compose.yml`, rebuild image, deploy
4. Prod `docker-compose.yml` stays untouched until release
5. Push to `origin/ie-vouchervault` for safekeeping
