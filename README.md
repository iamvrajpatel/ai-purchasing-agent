# AI Purchasing Agent

Full-stack FastAPI implementation of an AI-assisted buyer workflow. The application reviews purchasing recommendations, investigates operational evidence with tool calls, calculates safe replenishment decisions, requests approval when needed, executes purchase orders, and validates the result.

The frontend is a FastAPI/Jinja2 buyer dashboard. The backend owns all business logic, OpenAI tool-calling, PostgreSQL persistence, approvals, purchase-order execution, supplier simulation, and validation.

## Implemented Scope

- Scenario 1 end-to-end: recommendation `800`, calculated requirement `650`, decision `MODIFY`.
- Split sourcing: one recommendation can produce separate supplier proposals, approvals, and purchase orders.
- Scenario 2 recovery: partial supplier fulfillment creates a shortfall analysis, recovery case, and supplemental sourcing path.
- Direct OpenAI API integration through the official OpenAI Python SDK.
- Human approval for proposals above `PURCHASE_AUTO_APPROVAL_LIMIT`.
- Idempotent purchase-order execution.
- Post-execution order validation and supplier outcome validation.
- Deterministic constraints for budget, MOQ, order multiple, supplier availability, storage volume, delivery timing, missing data, and duplicate-safe execution.
- Demo data for additional realistic buyer situations: demand spike, storage pressure, long lead time, supplier shortage, and budget pressure.

## Submission Checklist

| Requirement | Repository Artifact |
| --- | --- |
| Complete source code | `backend/` and `frontend/` |
| Setup and run instructions | This `README.md` |
| Architecture diagram | Mermaid diagram below and [docs/architecture.md](docs/architecture.md) |
| Description of approach | This README and [docs/Agent_Behaviour.md](docs/Agent_Behaviour.md) |
| Test scenarios and evaluation approach | [Test Scenarios and Evaluation](#test-scenarios-and-evaluation) and [docs/evaluation.md](docs/evaluation.md) |
| Mock APIs, datasets, and supporting services | Docker PostgreSQL, demo data scripts, seeded purchasing data, and in-process mock supplier adapter |
| Explanation of how agent decisions are validated | [How We Validate Agent Decisions](#how-we-validate-agent-decisions) and [docs/Feedback_Validation_Loop.md](docs/Feedback_Validation_Loop.md) |
| Working demo | [Working Demo Flow](#working-demo-flow) |
| Required environment variables | Root [.env.example](.env.example) |

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

## Reviewer Documentation

- [Agent behaviour](docs/Agent_Behaviour.md)
- [Feedback and validation loop](docs/Feedback_Validation_Loop.md)
- [Evaluation](docs/evaluation.md)

## Prerequisites

- Python 3.12+
- Local PostgreSQL server for the recommended command-line run
- Docker and Docker Compose only if using the optional containerized run
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
PUBLIC_BACKEND_URL=http://localhost:8000

OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini
OPENAI_TEMPERATURE=0
```

Notes:

- `DATABASE_URL` is used by the backend, Alembic, reset script, and diagnostic scripts.
- `BACKEND_API_URL` is used by the frontend to call the backend.
- `PUBLIC_BACKEND_URL` documents the browser-visible backend URL for local/Docker demos.
- `OPENAI_API_KEY` is required only when you click **Analyze with AI**.
- `OPENAI_MODEL` and `OPENAI_TEMPERATURE` control the direct OpenAI SDK call.
- For the recommended command-line workflow below, use `127.0.0.1` in `DATABASE_URL`.

## Option A: Command-Line Local Run

This is the recommended development/demo flow. Backend and frontend both run directly with `uvicorn`, and PostgreSQL runs as a local service.

### 1. Start Local PostgreSQL

On Linux:

```bash
sudo service postgresql start
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'rootroot';"
sudo -u postgres createdb ai_purchasing
```

If the database already exists, `createdb` may print an error. That is fine; continue with the backend setup.

On macOS with Homebrew PostgreSQL:

```bash
brew services start postgresql@16
createdb ai_purchasing
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

Use this only if you prefer running PostgreSQL, backend, and frontend in containers.

From the project root:

```bash
cp .env.example .env
```

For Docker Compose, containers must use service hostnames instead of `127.0.0.1`. In `.env`, set:

```env
DATABASE_URL=postgresql+psycopg://postgres:rootroot@postgres:5432/ai_purchasing
BACKEND_API_URL=http://backend:8000
PUBLIC_BACKEND_URL=http://localhost:8000
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini
OPENAI_TEMPERATURE=0
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

## Data Ingestion / Demo Reset

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

Expected healthy indicators after reset and verification:

```text
supplier_products: 17
recommendations: 6
Recommendation #1 SKU-101 ... supplier option(s) [OK]
SKU-101 decision=MODIFY, proposed_quantity=650
Warehouse capacity ... [OK]
```

Equivalent project-root wrappers:

```bash
bash scripts/reset_demo_db.sh
bash scripts/verify_demo_db.sh
bash scripts/diagnose_recommendations.sh
```

## Working Demo Flow

1. Start PostgreSQL, backend, and frontend.
2. Open `http://localhost:8001`.
3. Review the dashboard budget health and pending approval exposure.
4. Go to **Recommendations** and open **SKU-101 Organic Whole Milk 1L**.
5. Click **Analyze with AI**.
6. Expected result:

```text
Original recommendation: 800
Calculated requirement: 650
Decision: MODIFY
Estimated cost: 32500 for a single supplier path, or split supplier rows when the best supplier is short
Approval required: yes
```

7. On the agent run page, review product id/SKU/name, supplier id/name, quantities, cost, risks, and proof for any failed checks.
8. Go to **Approvals**.
9. Approve each supplier proposal independently.
10. Execute each approved proposal independently from the approval row.
11. Go to **Purchase Orders** and open the created order.
12. Review items, supplier response, and validation checks.
13. For Scenario 2, open a PO with partial supplier confirmation and use **Analyze Recovery** to inspect shortfall, alternate supplier options, escalation details, or supplemental PO proposal.

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

## How We Validate Agent Decisions

The system treats the AI output as an investigation result, not as final authority. The feedback loop is:

```text
AI investigates with restricted tools
-> deterministic backend validates the proposal
-> buyer approves the proposed action
-> backend revalidates current state
-> purchase order is created idempotently
-> supplier response is captured
-> validation records are persisted
-> recovery or escalation is created when the outcome differs
```

Key validation points:

- Tool calls are restricted and persisted in `agent_tool_calls`.
- `DecisionEngine` and `ConstraintEngine` recalculate requirements and constraints server-side.
- Approval records store the approved action snapshot, including product, supplier, warehouse, quantity, price, and total.
- Execution reruns constraints before creating a PO, so changed budget, supplier availability, delivery timing, or storage can block stale approvals.
- Purchase-order validation compares the persisted PO with the approved action.
- Supplier outcome validation detects partial confirmation, rejection, and mismatches.
- Scenario 2 recovery calculates shortfall and creates a recovery case for alternate sourcing, supplemental PO, no-action-required, or escalation.

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

Execute an approved run:

```bash
curl -X POST http://localhost:8000/api/v1/agent/runs/1/execute
```

Execute one approved proposal independently:

```bash
curl -X POST http://localhost:8000/api/v1/approvals/1/execute \
  -H 'x-buyer-user: buyer@example.com'
```

## Test Scenarios and Evaluation

```bash
cd /home/vrajpatel/personal/assessment/ai-purchasing-agent/backend
. .venv/bin/activate
python -m pytest
python -m compileall app
```

The test suite focuses on deterministic business behavior and uses fake/injected client behavior where needed instead of real OpenAI calls.

| Test File | What It Verifies |
| --- | --- |
| `test_decision_engine.py` | Scenario 1 `MODIFY 800 -> 650`, split sourcing, timely incoming PO calculations, no-feasible-supplier investigation, and labeled product/supplier evidence. |
| `test_constraint_engine.py` | Budget, MOQ, storage volume, late delivery with delayed-day proof, and volume-based warehouse occupancy. |
| `test_purchase_orders.py` | Approval execution, split execution, duplicate execution protection, stale budget blocking, persisted PO validation, and partial supplier fulfillment detection. |
| `test_recovery_service.py` | Scenario 2 shortfall calculation, alternate supplier sourcing, original supplier exclusion, no-action-required recovery, escalation, and supplemental PO execution. |
| `test_dashboard.py` | Dashboard budget health and pending approval exposure. |
| `test_tool_registry.py` | Specific tool schemas and filtering of irrelevant LLM tool arguments. |
| `test_agent_state.py` | State machine protection against illegal workflow transitions. |

Concrete evaluation coverage:

- Scenario 1 modifies an inflated recommendation from `800` to `650`.
- Split sourcing creates separate supplier actions, approvals, and POs.
- Individual approvals can be approved and executed independently.
- Duplicate execution returns existing POs instead of creating unsafe duplicates.
- Budget, storage, delivery, MOQ, order multiple, and supplier availability constraints are enforced.
- Constraint risks include proof such as budget overage, delayed days, supplier shortfall, and storage overage.
- Dashboard exposes warehouse budget health and pending approval exposure.
- Supplier partial fulfillment creates validation failure and Scenario 2 recovery.
- Recovery cases evaluate supplemental supplier sourcing, no-action-required, and escalation.
- Tool schemas and argument filtering prevent malformed LLM tool calls from breaking analysis.
- State transitions reject illegal workflow movement.

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
- Scenario 3-style edge cases are represented through demo data, reusable constraints, validation, and diagnostics.
- This is a local assignment demo, not production financial infrastructure.
