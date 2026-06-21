# VoucherVault Ireland — Live Balance Checking

**Fork:** https://github.com/raihatneloy/VoucherVault
**Upstream:** https://github.com/l4rm4nd/VoucherVault
**Deployed:** `192.168.86.47:8000`

---

## Target Retailers

| Retailer | Method | Endpoint | Status |
|----------|--------|----------|--------|
| Lidl Ireland | JSON POST | `lidl.ie/api/giftcards/balance` | 🟡 Planned |
| Dunnes Stores | JSON POST | `dunnesstores.com/api/giftcards/balance/` | 🟡 Planned |
| SuperValu | JSON POST | `supervalu.ie/api/giftcards/balance` | 🟡 Planned |
| Tesco Ireland | ASP.NET form | `tesco.ie/gift-cards/giftcardbalance/` | 🟡 Planned |
| Aldi Ireland | 3rd-party route | BIN-based detection | 🔴 Deferred |

---

## Phase 0: Foundation

- [x] **0.1 — Fork repo** → `raihatneloy/VoucherVault`
- [x] **0.2 — Set up remotes** → `origin` (SSH → fork), `upstream` (HTTPS → l4rm4nd)
- [x] **0.3 — Write implementation plan**
- [ ] **0.4 — Create `ie-vouchervault` branch** for all our changes

---

## Phase 1: Data Model

- [x] **1.1 — Add fields to `Item` model**
  - `balance_checker` (CharField: `lidl_ie`, `dunnes_ie`, `supervalu_ie`, `tesco_ie`, or `none`)
  - `last_checked_balance` (DecimalField, nullable)
  - `last_checked_at` (DateTimeField, nullable)
  - `live_balance` (DecimalField, nullable — the most recently fetched balance)
- [x] **1.2 — Generate & run migration**
- [x] **1.3 — Update `ItemForm`** → add `balance_checker` dropdown to create/edit forms
- [ ] **1.4 — Update `UserPreference` model** (optional) → `auto_check_balance` toggle

---

## Phase 2: Balance Checker Engine

- [x] **2.1 — Create `myapp/balance_checkers/` package**
  - `__init__.py`
  - `base.py` → abstract `BalanceChecker` class with `check_balance(card_number, pin) → BalanceResult`
  - `providers/` directory
- [x] **2.2 — Implement `LidlIEProvider`**
  - Fetches CSRF token from `lidl.ie/gift-cards/`
  - POSTs `{cardNumber, pin}` to `lidl.ie/api/giftcards/balance`
  - Parses `{status, balance, currency}`
- [ ] **2.3 — Implement `DunnesIEProvider`**
  - Fetches CSRF token from `dunnesstores.com/gift-cards/check-balance/`
  - POSTs `{card_number, security_code}` to `dunnesstores.com/api/giftcards/balance/`
  - Parses `{success, balance, currency}`
- [ ] **2.4 — Implement `SuperValuIEProvider`**
  - Fetches CSRF token from `supervalu.ie/gift-cards/balance/`
  - POSTs `{cardNumber, securityCode}` to `supervalu.ie/api/giftcards/balance`
  - Parses `{balance, currency}`
- [ ] **2.5 — Implement `TescoIEProvider`**
  - GET `tesco.ie/gift-cards/giftcardbalance/`, parse `__VIEWSTATE`/`__EVENTVALIDATION`
  - POST back form data + card details
  - Scrape balance from returned HTML
- [x] **2.6 — Build `ProviderRegistry`**
  - Maps `balance_checker` string → provider class
  - `get_provider(checker_type) → BalanceChecker`

---

## Phase 3: API & View Integration

- [x] **3.1 — Add `check_balance` view** (POST endpoint)
  - Takes `item_uuid`, calls provider, updates `last_checked_balance`/`last_checked_at`
  - Returns JSON: `{success, balance, currency, error}`
- [x] **3.2 — Add URL route** → `POST /items/<uuid:item_uuid>/check-balance/`
- [x] **3.3 — Update `view-item.html`**
  - Show "Check Balance" button (only for gift cards with a balance checker set)
  - Display live balance with timestamp
  - Loading state while checking
  - Error display
- [ ] **3.4 — Update `inventory.html`**
  - Show live balance column/indicator in gift card list
  - Small "refresh" icon per row
- [ ] **3.5 — Update `dashboard.html`**
  - Aggregate live balances in total value display

---

## Phase 4: Automation & Reliability

- [ ] **4.1 — Add Celery task** → `refresh_all_balances()`
  - Iterates all items with a `balance_checker` set
  - Calls provider, saves result
- [ ] **4.2 — Add Celery Beat schedule** (optional)
  - E.g. daily refresh at 6 AM
- [ ] **4.3 — Add management command** → `python manage.py check_balances`
  - For manual/adhoc runs
- [ ] **4.4 — Rate limiting & caching**
  - Don't re-check balance within 5 minutes of a check
  - Respect retailer rate limits (delay between checks)

---

## Phase 5: Polish & Edge Cases

- [ ] **5.1 — Error messages** → user-friendly when balance check fails
- [ ] **5.2 — Dark mode support** for new UI elements
- [ ] **5.3 — Handle expired/used cards gracefully** (don't show check button)
- [ ] **5.4 — Handle card with no `pin`** (some retailers need PIN, some don't)
- [ ] **5.5 — Test with real gift cards** 🎯
- [ ] **5.6 — Documentation update** (README, settings)

---

## How to Track Progress

Each commit closes one task (e.g. `git commit -m "1.1: Add balance_checker fields to Item model"`).
Run `cat PLAN.md` anytime to see the latest status.

## Implementation Notes

### Lidl Ireland API (June 2026)

**API endpoint**: `POST https://www.lidl.ie/explore/giftyBalanceV2/gifty`
**Payload**: `{cardNumber, pinNumber, country: "IE", locale: "en-IE", frcCaptchaToken: "...",}`
**Balance**: Amount in cents (5000 = 50.00 EUR)
**Balance check page**: `https://www.lidl.ie/c/gift-card-balance-check/s10073374`
**Friendly Captcha**: Required (sitekey `FCMGDDIJTON17UAD`). A modal with the widget opens when user clicks "Check Balance" — auto-solves via PoW in the browser in 1-3 seconds.
