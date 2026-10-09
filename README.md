# AI Purchasing Agent

Full-stack FastAPI implementation of an AI-assisted buyer workflow. The application reviews purchasing recommendations, investigates operational evidence with tool calls, calculates safe replenishment decisions, requests approval when needed, executes purchase orders, and validates the result.

The frontend is a FastAPI/Jinja2 buyer dashboard. The backend owns all business logic, OpenAI tool-calling, PostgreSQL persistence, approvals, purchase-order execution, supplier simulation, and validation.

## Implemented Scope

- Scenario 1 end-to-end: recommendation `800`, calculated requirement `650`, decision `MODIFY`.
- Direct OpenAI API integration through the official OpenAI Python SDK.
- Human approval for proposals above `PURCHASE_AUTO_APPROVAL_LIMIT`.
- Idempotent purchase-order execution.
- Post-execution order validation and supplier outcome validation.
- Deterministic constraints for budget, MOQ, order multiple, supplier availability, storage volume, delivery timing, missing data, and duplicate-safe execution.
- Demo data for additional realistic buyer situations: demand spike, storage pressure, long lead time, supplier shortage, and budget pressure.

## Architecture

```mermaid
flowchart TD
    Buyer[Buyer] --> FE[Frontend FastAPI/Jinja2 :8001]
    FE -->|HTTP / same-origin proxy| BE[Backend FastAPI :8000]
    BE --> Agent[OpenAI Tool-Calling Agent]
    Agent --> Tools[Restricted Backend Tools]
    Tools --> Services[Deterministic Business Services]
    BE --> Services
    Services --> DB[(PostgreSQL)]
    Services --> Supplier[Mock Supplier Adapter]
    Supplier --> Validation[Validation + Recovery]
    Validation --> DB
```

More detail is in [docs/architecture.md](docs/architecture.md).

## Prerequisites

- Python 3.12+
- Docker and Docker Compose, or a local PostgreSQL server
- OpenAI API key for live agent analysis
- Two terminal windows: one for backend, one for frontend

## Environment Setup

Create the root environment file:

```bash
cd /home/vrajpatel/personal/assessment/ai-purchasing-agent
cp .env.example .env
```

For the current local demo workflow, these are the important values:

```env
DATABASE_URL=postgresql+psycopg://postgres:rootroot@127.0.0.1:5432/ai_purchasing
BACKEND_API_URL=http://localhost:8000

OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini
OPENAI_TEMPERATURE=0
```

Notes:

- `DATABASE_URL` is used by the backend, Alembic, reset script, and diagnostic scripts.
- `BACKEND_API_URL` is used by the frontend to call the backend.
- `OPENAI_API_KEY` is required only when you click **Analyze with AI**.
- For the manual local workflow below, use `127.0.0.1` in `DATABASE_URL`.

## Option A: Manual Local Run

This is the recommended development/demo flow because it makes logs easy to read.

### 1. Start PostgreSQL

From the project root:

```bash
docker compose up -d postgres
```

### 2. Set Up Backend

```bash
cd /home/vrajpatel/personal/assessment/ai-purchasing-agent/backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Load a clean demo database:

```bash
python app/reset_demo_db.py
python app/verify_demo_db.py
python app/diagnose_recommendations.py
```

Expected healthy demo indicators:

```text
supplier_products: 17
Recommendation #1 SKU-101 ... 4 supplier option(s) [OK]
SKU-101 decision=MODIFY, proposed_quantity=650
```

Start the backend:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Backend URL:

```text
http://localhost:8000
```

### 3. Set Up Frontend

Open a second terminal:

```bash
cd /home/vrajpatel/personal/assessment/ai-purchasing-agent/frontend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Frontend URL:

```text
http://localhost:8001
```

## Option B: Docker Compose Run

From the project root:

```bash
cp .env.example .env
```

For Docker Compose, containers must use service hostnames instead of `127.0.0.1`. In `.env`, set:

```env
DATABASE_URL=postgresql+psycopg://postgres:rootroot@postgres:5432/ai_purchasing
BACKEND_API_URL=http://backend:8000
PUBLIC_BACKEND_URL=http://localhost:8000
```

Then start the stack:

```bash
docker compose up --build
```

In another terminal:

```bash
docker compose exec backend python -m app.reset_demo_db
docker compose exec backend python -m app.verify_demo_db
docker compose exec backend python -m app.diagnose_recommendations
```

Then open:

```text
Frontend: http://localhost:8001
Backend:  http://localhost:8000
```

## Demo Data Commands

Use these from the backend directory:

```bash
python app/reset_demo_db.py
```

Drops all tables, recreates schema, and loads clean demo data.

```bash
python app/demo_data.py
```

Upserts demo data into an existing schema without dropping tables.

```bash
python app/verify_demo_db.py
```

Checks table counts, supplier options, and warehouse capacity.

```bash
python app/diagnose_recommendations.py
```

Prints requirement, supplier options, constraint results, and final deterministic decision for every recommendation.

Equivalent project-root wrappers:

```bash
bash scripts/reset_demo_db.sh
bash scripts/verify_demo_db.sh
bash scripts/diagnose_recommendations.sh
```

## Recommended Demo Flow

1. Start PostgreSQL, backend, and frontend.
2. Open `http://localhost:8001`.
3. Go to **Recommendations**.
4. Open **SKU-101 Organic Whole Milk 1L**.
5. Click **Analyze with AI**.
6. Expected result:

```text
Original recommendation: 800
Calculated requirement: 650
Decision: MODIFY
Supplier: Acme Wholesale
Estimated cost: 32500
Approval required: yes
```

7. Go to **Approvals**.
8. Approve the proposal.
9. Return to the agent run page and click **Execute Approved Order**.
10. Go to **Purchase Orders** and open the created order.
11. Review items, supplier response, and validation checks.

## Scenario 1 Calculation

The stable demo recommendation is SKU-101 in North Fulfillment:

```text
forecast demand:          900
safety stock:             100
sellable inventory:      -200
timely incoming PO:      -150
--------------------------------
required quantity:        650
```

The original recommendation is `800`, so the deterministic decision is:

```text
MODIFY 800 -> 650
```

The selected supplier has unit price `50`, so:

```text
650 * 50 = 32500
```

Because `32500 > PURCHASE_AUTO_APPROVAL_LIMIT=20000`, human approval is required.

## API Examples

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/recommendations
curl http://localhost:8000/api/v1/dashboard/summary
```

Analyze recommendation:

```bash
curl -X POST http://localhost:8000/api/v1/agent/analyze \
  -H 'content-type: application/json' \
  -d '{"recommendation_id":1}'
```

Approve proposal:

```bash
curl -X POST http://localhost:8000/api/v1/approvals/1/approve \
  -H 'x-buyer-user: buyer@example.com'
```

Execute approved run:

```bash
curl -X POST http://localhost:8000/api/v1/agent/runs/1/execute
```

## Tests

```bash
cd /home/vrajpatel/personal/assessment/ai-purchasing-agent/backend
. .venv/bin/activate
python -m pytest
python -m compileall app
```

The test suite focuses on deterministic business behavior and uses fake/injected client behavior where needed instead of real OpenAI calls.

## Troubleshooting

### Backend returns `503 Service Unavailable`

The backend is running, but it cannot connect to PostgreSQL.

Check:

```bash
docker compose ps
cat ../.env | grep DATABASE_URL
python app/verify_demo_db.py
```

Make sure `DATABASE_URL` points to the active PostgreSQL user/password/database.

### `supplier_products = 0`

The supplier catalog was not loaded. The agent cannot select a supplier and executable recommendations may become `INVESTIGATION_REQUIRED`.

Fix:

```bash
python app/reset_demo_db.py
python app/verify_demo_db.py
```

The app uses the plural table name:

```text
supplier_products
```

### `OPENAI_API_KEY is required`

The backend can run without an OpenAI key, but live analysis cannot.

Fix root `.env`:

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini
```

Restart the backend after changing `.env`.

### Old analysis still shows `INVESTIGATION_REQUIRED`

You may be viewing an old `agent_run`. After resetting data, start a fresh analysis from the recommendation detail page and open the newest run.

### Frontend cannot reach backend

Confirm backend is running on port `8000` and root `.env` has:

```env
BACKEND_API_URL=http://localhost:8000
```

Restart the frontend after changing `.env`.

## Known Limitations

- Authentication is a documented mock buyer identity for local demo purposes.
- The supplier integration is an in-process mock adapter.
- Scenario 2 and 3 are represented through demo data, constraints, validation, and diagnostics rather than separate full workflows.
- This is a local assignment demo, not production financial infrastructure.
