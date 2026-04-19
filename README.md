# Semestrální práce předmětu STIN — Měnové kurzy

| Autor |
|-------|
| Parrot2CZE |

[![codecov](https://codecov.io/gh/[GITHUB_USERNAME]/[REPO_NAME]/graph/badge.svg?token=[CODECOV_TOKEN])](https://codecov.io/gh/[GITHUB_USERNAME]/[REPO_NAME])

**[Odkaz na nasazené řešení](https://stin-exchange-rate-cgbce4cthth0d4b5.francecentral-01.azurewebsites.net/) 💱**

---

## Tech Stack

- **Backend:** Python 3.11, Flask 3.1
- **Frontend:** HTML + Bootstrap 5, Chart.js
- **Cache:** Flask-Caching (SimpleCache)
- **Rate limiting:** Flask-Limiter
- **Auth:** bcrypt session-based login
- **CI/CD:** GitHub Actions → Azure App Service
- **Testy:** pytest + pytest-cov → Codecov

---

## Funkce aplikace

### FR1 — Aktuální měnové kurzy
Aplikace volá REST API [exchangerate.host](https://exchangerate.host/) a ukládá odpověď do cache (výchozí TTL 20 minut). Uživatel si zvolí základní měnu z nabídky.

### FR2 — Nejsilnější měna
Nejsilnější měna vůči zvolené základní je ta s **nejnižším kurzem** (tj. za 1 jednotku základní měny dostanete nejméně jednotek cizí měny — kupní síla je tedy nejvyšší).

### FR3 — Nejslabší měna
Analogicky měna s **nejvyšším kurzem** vůči základní — za 1 jednotku základní měny dostanete nejvíce jednotek cizí měny.

### FR4 — Průměr kurzů za období
Zadáte základní měnu, seznam porovnávaných měn a počet dní (1–365). Aplikace stáhne historická data a pro každou měnu vypočítá **aritmetický průměr kurzu** za dané období.

---

## Spuštění lokálně

### Požadavky
- Python 3.11+
- API klíč pro [exchangerate.host](https://exchangerate.host/)

### Windows

```bash
py -3 -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Zkopíruj `.env.example` → `.env` a doplň API klíč:

```
EXCHANGERATE_API_KEY=tvuj_klic
SECRET_KEY=nejake-tajne-heslo
FLASK_ENV=development
```

Spuštění:

```bash
flask run
```

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # doplň hodnoty
flask run
```

---

## Konfigurace

Aplikace se konfiguruje přes `config.yml` v kořeni projektu. Klíčové sekce:

| Sekce | Popis |
|---|---|
| `api_keys.exchangerate` | API klíč (přebíjí env proměnnou) |
| `currencies.base` | Dostupné základní měny v UI |
| `currencies.compare` | Měny k porovnání |
| `cache.timeout_seconds` | TTL cache v produkci (výchozí 1200 s) |
| `rate_limit.default` | Globální rate limit (výchozí 60/min) |
| `rate_limit.button_cooldown_seconds` | Cooldown tlačítka v UI |
| `users` | Uživatelé s bcrypt hashem hesla |
| `i18n` | Překlady UI (cs / en) |

Vygenerování bcrypt hashe hesla:

```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'heslo', bcrypt.gensalt()).decode())"
```

---

## Spouštění testů

```bash
pytest
```

Testy s coverage reportem:

```bash
pytest --cov=app --cov-report=term-missing --cov-report=html
```

Coverage report se otevře v `htmlcov/index.html`.

Požadavek projektu: **≥ 80 % pokrytí** — vynuceno v `pytest.ini` i CI pipeline.

---

## API endpointy

| Endpoint | Metoda | Popis |
|---|---|---|
| `/` | GET / POST | Hlavní UI — výběr měn a zobrazení výsledků |
| `/login` | GET / POST | Přihlašovací formulář |
| `/logout` | GET | Odhlášení |
| `/lang/<lang>` | GET | Přepnutí jazyka (`cs` / `en`) |
| `/api/latest` | GET | Aktuální kurzy (`?base=EUR&symbols=USD,CZK`) |
| `/api/strongest` | GET | Nejsilnější měna (`?base=EUR&symbols=USD,CZK,JPY`) |
| `/api/weakest` | GET | Nejslabší měna (`?base=EUR&symbols=USD,CZK,JPY`) |
| `/api/average` | GET | Průměr za N dní (`?base=EUR&symbols=USD,CZK&days=7`) |
| `/api/logs` | GET | Systémové logy (vyžaduje přihlášení) |

---

## CI/CD pipeline

Pipeline má dva joby:

```
push na main
    │
    ▼
🧪 test
  ├─ checkout + Python 3.11
  ├─ pip install
  ├─ pytest (--cov-fail-under=80)
  ├─ upload coverage → Codecov
  └─ upload coverage.xml jako artefakt
    │
    ▼ (pouze pokud test prošel)
🚀 deploy
  ├─ Azure login (OIDC — bez uložených hesel)
  └─ azure/webapps-deploy → STIN-exchange-rate / Production
```

PR na main spustí pouze `test` job (bez deploye).

### Potřebné GitHub Secrets

| Secret | Popis |
|---|---|
| `CODECOV_TOKEN` | Token z codecov.io pro upload coverage |
| `AZUREAPPSERVICE_CLIENTID_...` | Client ID Azure service principal |
| `AZUREAPPSERVICE_TENANTID_...` | Tenant ID Azure |
| `AZUREAPPSERVICE_SUBSCRIPTIONID_...` | Subscription ID Azure |
| `EXCHANGERATE_API_KEY` | Klíč pro exchangerate.host (volitelné — lze dát do config.yml) |
| `SECRET_KEY` | Flask secret key pro session |

---

## Bezpečnost

- Session-based autentizace (bcrypt hash hesel v `config.yml`)
- Rate limiting na všech API endpointech (Flask-Limiter)
- Content Security Policy hlavička v base šabloně
- Validace všech vstupů (`app/validators.py`) — ochrana proti injection
- HTTPS v produkci (Azure App Service)
- API logy přístupné pouze přihlášeným uživatelům

---

## Struktura projektu

```
├── app/
│   ├── __init__.py          # Factory funkce create_app()
│   ├── api.py               # REST API Blueprint (/api/*)
│   ├── routes.py            # UI Blueprint (/, /login, ...)
│   ├── services/
│   │   └── exchange_rate.py # Logika volání exchangerate.host
│   ├── auth.py              # Login / logout / session
│   ├── validators.py        # Validace vstupů
│   ├── config.py            # Flask config třídy
│   ├── extensions.py        # Limiter, Cache, CORS
│   ├── logger.py            # In-memory + file logger
│   ├── app_config_loader.py # Čtení config.yml
│   └── templates/           # Jinja2 šablony (base, index, login)
├── tests/
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_auth.py
│   ├── test_exchange_rate_service.py
│   ├── test_logger.py
│   ├── test_routes.py
│   └── test_validators.py
├── .github/workflows/
│   └── ci-cd.yml            # Sjednocená CI/CD pipeline
├── config.yml               # Konfigurace aplikace
├── requirements.txt
├── run.py
└── startup.txt              # Gunicorn příkaz pro Azure
```
