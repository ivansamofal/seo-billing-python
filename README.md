# seo-billing-python

Connects to the shared MySQL database, fetches per-user account data from BM Common API, calculates each user's daily charge based on usage (unique phrases, accounts, projects), and applies a batch deduction in a single atomic transaction.

---

## Requirements

- Python 3.12+
- MySQL 5.7+ (shared `wb` database)
- Access to BM Common API

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# fill in .env with real credentials
```

---

## Configuration

All configuration is read from environment variables (or a `.env` file).

| Variable | Required | Default | Description |
|---|---|---|---|
| `DB_HOST` | yes | — | MySQL host |
| `DB_PORT` | no | `3306` | MySQL port |
| `DB_NAME` | yes | — | Database name |
| `DB_USERNAME` | yes | — | MySQL user |
| `DB_PASSWORD` | yes | — | MySQL password |
| `BM_COMMON_API_URL` | yes | — | BM Common API base URL |
| `BM_COMMON_API_TOKEN` | yes | — | BM Common API token (used as Basic Auth username) |
| `APP_ENV` | no | `prod` | Environment tag (`dev` / `prod`) |
| `FREE_DAYS` | no | `3` | Free days after registration for all users |
| `FREE_DAYS_API_ENTERED` | no | `7` | Free days for users with a valid bidder token |
| `HISTORY_TXT` | no | `Списание абоненсткой платы` | Description written to billing history |

---

## Usage

```bash
# Charge users for today
python -m src.main update-balance

# Charge users for a specific date
python -m src.main update-balance --date 2024-01-15

# Enable debug logging
python -m src.main --verbose update-balance
```

### Docker

```bash
# Build
docker build -t seo-billing-python .

# Run for today
docker run --env-file .env seo-billing-python

# Run for a specific date
docker run --env-file .env seo-billing-python \
  python -m src.main update-balance --date 2024-01-15

# Via docker compose
docker compose run --rm seo-billing-python \
  python -m src.main update-balance
```

---

## Billing Logic

### 1. Eligible users

Users are selected when all of the following are true:
- `confirmed = 1`
- `tariffStatus > 0` (tariff selected)
- `balance > 0`
- `blocked = 0` (or NULL)

### 2. Exclusions (no charge)

A user is skipped if any of the following apply:

- **Bonus period** — within `FREE_DAYS` (3) days of `regDate`, or within `FREE_DAYS_API_ENTERED` (7) days if a valid bidder token is confirmed by BM Common API.
- **Active promocode** — has a `promocodes` row whose `DATE_ADD(dt, INTERVAL value DAY) >= CURDATE()`.

### 3. Tariff classification

| Tariff | Condition |
|---|---|
| **FREE** | ≤ 500 unique phrases AND ≤ 1 account AND ≤ 1 project |
| **FREE** | `salesMonth` ≤ 300k AND weekly sales ≤ 200k AND unique phrases ≤ 900 |
| **HELP** | API confirms `supportTariff`, phrases < 900, ≤ 1 bidder account, ≤ 1 sales account, ≤ 3 projects, weekly sales ≤ 200k |
| **PAID** | everything else |

FREE and HELP users are not charged.

### 4. PAID price calculation

```
total = base_phrase_price + account_surcharge + project_surcharge
```

**Base price by unique phrases:**

| Phrases | Rubles/day |
|---|---|
| ≤ 500 | 0 |
| 501 – 5 000 | 217 |
| 5 001 – 8 000 | 237 |
| 8 001 – 10 000 | 297 |
| 10 001 – 15 000 | 337 |
| 15 001 – 20 000 | 437 |
| 20 001 – 30 000 | 617 |
| 30 001 – 50 000 | 917 |
| 50 001 – 100 000 | 1 683 |
| 100 001+ | 2 000 |

**Account surcharge:** +50 rubles/day for each account beyond the first.
If the user has more than 1 account but ≤ 500 phrases, base price is raised to at least 217.

**Project surcharge** (over 5 projects):

| Projects | Rubles per extra project |
|---|---|
| 6 – 20 | 66 |
| 21 – 40 | 33 |
| 41 – 100 | 17 |
| 101+ | 8 |

### 5. Batch deduction

All charges are applied in a single atomic transaction using a temporary table:

```sql
CREATE TEMPORARY TABLE temp_user_balance_updates (user_id INT, amount INT, PRIMARY KEY (user_id));
INSERT INTO temp_user_balance_updates VALUES (...);
UPDATE users u
  INNER JOIN temp_user_balance_updates tmp ON u.id = tmp.user_id
  SET u.balance = GREATEST(0, CAST(ROUND(u.balance) AS SIGNED) - tmp.amount;
INSERT INTO history (user_id, dt, txt, amount, hint) VALUES (...);
DROP TEMPORARY TABLE temp_user_balance_updates;
```

This keeps balance non-negative, avoids floating-point drift, and reduces database round-trips to a constant number regardless of user count.

---

## Project Structure

```
src/
├── main.py                          # CLI entry point (click)
├── config/
│   ├── settings.py                  # Env-var config
│   └── database.py                  # SQLAlchemy engine + session factory
├── models/
│   ├── user.py                      # User / UserWithProjects dataclasses
│   └── history.py                   # HistoryEntry dataclass
├── repositories/
│   └── user_repository.py           # All DB queries including batch ops
├── domain/pricing/
│   └── tariff_pricing_strategy.py   # FREE / HELP / PAID classification and price calculation
└── services/
    ├── billing_service.py           # Orchestration: fetch → filter → calculate → commit
    └── external_api_service.py      # BM Common API client (httpx)
```

---

## External API

BM Common API is called once per billing run with all user emails:

**`POST /auth/auth/seo/infos`** — returns per-user account list, weekly sales sum, and support tariff flag.

Authentication is Basic Auth with `BM_COMMON_API_TOKEN` as the username. All requests time out after 10 seconds. On failure the service logs a warning and proceeds with empty external data (users will be classified as FREE where applicable).
