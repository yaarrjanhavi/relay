# Relay: A Self-Learning Bayesian LLM Router

> **One-line pitch:** A production-grade FastAPI service that dynamically classifies prompts and routes each request to the cheapest Google Gemini tier that is "good enough", learning online from human thumbs up/down feedback via Thompson Sampling to cut LLM costs by ~70% while maintaining near-Pro quality.

---

## 1. The Problem

Modern AI systems face a stark trade-off:
- **Always using the flagship model** (e.g. `gemini-2.5-pro` at $10.00/1M output tokens) yields reliable quality but wastes huge budgets on simple summarization, extraction, and chit-chat.
- **Always using lightweight models** (e.g. `gemini-2.5-flash-lite` at $0.40/1M output tokens) cuts cost by 96% but fails hard on complex math, intricate code refactoring, or critical multi-step reasoning.
- **Static routing rules** are brittle, require manual tuning, and fail to adapt as prompt distributions shift or model capabilities improve over time.

**Relay** solves this by formulating model selection as a contextual multi-armed bandit. It maintains Bayesian Beta posteriors for every `(category, tier)` pair, samples via cost-penalized Thompson Sampling, applies continuous time decay toward uninformative priors, and enforces a non-negotiable safety lock for high-stakes domains.

---

## 2. Architecture Diagram

```
                             +-----------------------+
                             |   Client Application   |
                             +-----------+-----------+
                                         |
                                         | (POST /v1/route with Idempotency-Key)
                                         v
+-----------------------------------------------------------------------------------+
|                                  RELAY SERVICE                                    |
|                                                                                   |
|   +---------------------+   +---------------------+   +-----------------------+   |
|   |  Token Bucket Rate  |   |  Response Cache     |   |  Safety Classifier    |   |
|   |  Limiter (120 rpm)  |-->|  (SHA-256 / 30m)    |-->|  - High-Stakes Regex  |   |
|   |  [Redis / FailOpen] |   |  [Redis / FailOpen] |   |  - Embedding Centroid |   |
|   +---------------------+   +---------------------+   +-----------+-----------+   |
|                                                                   |               |
|                                         +-------------------------+               |
|                                         |                                         |
|                                         v                                         |
|                       +-----------------------------------+                       |
|                       |   Bayesian Bandit Engine          |                       |
|                       |   - Time Decay (0.98^days)        |                       |
|                       |   - Cost-Penalized Thompson Sample|                       |
|                       |   - Safety Lock for High-Stakes   |                       |
|                       +-----------------+-----------------+                       |
|                                         |                                         |
|                                         v                                         |
|                       +-----------------------------------+                       |
|                       |   Fallback Escalation Chain       |                       |
|                       |   Small -> Medium -> Large        |                       |
|                       +-----------------+-----------------+                       |
+-----------------------------------------|-----------------------------------------+
                                          |
            +-----------------------------+-----------------------------+
            |                             |                             |
            v                             v                             v
  +--------------------+        +--------------------+        +--------------------+
  | Gemini Flash-Lite  |        |    Gemini Flash    |        |     Gemini Pro     |
  | (Small Tier: $0.40)|        | (Medium Tier: $2.5)|        | (Large Tier: $10.0)|
  +--------------------+        +--------------------+        +--------------------+
            |                             |                             |
            +-----------------------------+-----------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        TRANSACTIONAL FEEDBACK LOOP                                |
|                                                                                   |
|  POST /v1/feedback  -->  [ SQLite Atomic Transaction: Feedback + Outbox ]         |
|                                    |                                              |
|                                    v                                              |
|                           [ Async Outbox Worker ]                                 |
|                                    |                                              |
|                   +----------------+----------------+                             |
|                   | (Success)                       | (After 5 Retries)           |
|                   v                                 v                             |
|          [ Update Arm Posterior &          [ Dead-Letter Table ]                  |
|            Posterior History ]                                                    |
+-----------------------------------------------------------------------------------+
```

---

## 3. The Math

### A. Posterior Expectation & Variance
For each `(category, tier)` arm, Relay maintains a $\text{Beta}(\alpha, \beta)$ distribution initialized to the flat uninformative prior $\text{Beta}(1, 1)$:

$$\mathbb{E}[\theta] = \frac{\alpha}{\alpha + \beta}$$

$$\text{Var}(\theta) = \frac{\alpha \beta}{(\alpha + \beta)^2 (\alpha + \beta + 1)}$$

### B. Thompson Sampling with Cost Penalty
Relay draws a random sample $\theta \sim \text{Beta}(\alpha_{\text{eff}}, \beta_{\text{eff}})$ for each candidate tier and computes an objective score penalizing normalized model cost:

$$\text{Score}(\text{tier}) = \theta - \lambda \cdot \left(\frac{\text{tier\_cost}}{\text{max\_tier\_cost}}\right)$$

- $\lambda = 0.25$ (configurable trade-off factor).
- The tier achieving $\max \text{Score}(\text{tier})$ is selected.

### C. Continuous Time Decay
To prevent early beliefs from locking the router into stale choices as models improve or drift, evidence decays toward prior parameters $\alpha_0=1, \beta_0=1$ with daily retention factor $R = 0.98$:

$$\alpha_{\text{eff}} = 1 + (0.98)^{\Delta t_{\text{days}}} \cdot (\alpha_{\text{stored}} - 1)$$

$$\beta_{\text{eff}} = 1 + (0.98)^{\Delta t_{\text{days}}} \cdot (\beta_{\text{stored}} - 1)$$

Time decay is evaluated dynamically on read and on update using an injectable wall-clock timestamp parameter (`now is None` pattern).

### D. Credible Intervals & Cold Start Indicator
The $90\%$ Bayesian credible interval is computed analytically and clipped to $[0, 1]$:

$$\text{CI}_{90} = \left[ \max\left(0, \mu - 1.645 \sigma\right), \; \min\left(1, \mu + 1.645 \sigma\right) \right]$$

When cumulative evidence $E = (\alpha + \beta - 2) < 10$, the arm is flagged with an active **"Cold start"** badge on the dashboard.

### E. Safety Rule (Non-Negotiable)
Any prompt falling into the `high_stakes` category (legal, medical, financial, tax, investment, contract, dosage, diagnosis):
1. **Always** routes to the `large` tier (`gemini-2.5-pro`).
2. **Never** explores small or medium tiers.
3. Feedback submitted on `high_stakes` requests **never** alters any posterior in the database.
4. Auto-judge sampling is **strictly bypassed**.

---

## 4. API Endpoints

| Method | Path | Description | Key Parameters / Headers |
|---|---|---|---|
| `POST` | `/v1/route` | Route a prompt to optimal tier | Body: `{prompt: str}` (1..20000 chars), Header: `Idempotency-Key` |
| `POST` | `/v1/feedback` | Submit thumbs up/down | Body: `{request_id: str, thumbs_up: bool}` (Idempotent) |
| `GET` | `/v1/stats` | Decayed posteriors, CI90, evidence | Query: none |
| `GET` | `/v1/history` | Time series of posterior changes | Query: `limit` (default 1000) |
| `GET` | `/v1/system/metrics` | Latency (p50/p95), cache hits, savings | Query: none |
| `GET` | `/v1/admin/dead-letters`| Failed outbox events | Query: none |
| `POST` | `/v1/benchmark/replay` | Execute multi-seed benchmark | Query: `mode=simulated\|real`, `seeds=10` |
| `GET` | `/healthz` | Health check endpoint | Returns `{"status": "ok"}` |

---

## 5. Verified Gemini Models & Current Pricing Table

> **Note to operators:** Pricing is maintained in [`app/config.py`](file:///c:/Users/user/OneDrive/Documents/relay/app/config.py). Always periodically re-verify prices at [https://ai.google.dev/pricing](https://ai.google.dev/pricing).

| Tier | Gemini Model ID | Class | Input / 1M Tokens | Output / 1M Tokens |
|---|---|---|---|---|
| `small` | `gemini-2.5-flash-lite` | Flash-Lite class | \$0.10 | \$0.40 |
| `medium` | `gemini-2.5-flash` | Flash class | \$0.30 | \$2.50 |
| `large` | `gemini-2.5-pro` | Pro class | \$1.25 | \$10.00 |
| `embedding` | `gemini-embedding-001` | Embeddings | \$0.00 (Standard) | - |

---

## 6. Honest Benchmark Results

The benchmark was executed using `scripts/build_eval_grades.py` across **200 curated evaluation prompts** spanning 5 categories (adapted from HumanEval, GSM8K, CNN/DailyMail, UltraChat, and Medical/Legal benchmarks). 

Evaluation follows a strict protocol:
- **70/30 train/test split** (140 train prompts, 60 held-out test prompts).
- Metrics evaluated **strictly on the held-out 30% test set**.
- Repeated over **10 distinct random seeds**.

### Held-Out Test Set Comparison (10 Seeds, Mean ± Std)

| Strategy | Mean Quality | Quality Std | Mean Cost (USD) | Cost Std | Cost Saved vs Large (%) |
|---|---|---|---|---|---|
| **Always Large** (`gemini-2.5-pro`) | **91.7%** | ± 2.7% | \$0.0391 | ± \$0.0007 | 0.0% (Baseline) |
| **Relay Router** (Ours) | **86.5%** | ± 6.6% | **\$0.0118** | ± \$0.0013 | **69.9% ± 3.2%** |
| **Random Baseline** | 87.0% | ± 5.5% | \$0.0185 | ± \$0.0017 | 52.7% ± 3.7% |
| **Always Small** (`gemini-2.5-flash-lite`) | 73.8% | ± 4.9% | \$0.0067 | ± \$0.0018 | 82.9% ± 4.4% |

### Key Findings
1. **Near-Pro Quality with Major Savings:** Relay achieves **86.5% quality** (within 5.2% of Always-Large) while slashing API expenditure by **69.9%**.
2. **Failure of Always-Small:** While Always-Small saves 82.9% cost, response quality collapses to **73.8%** due to poor reasoning on code and math.
3. **Superiority over Uniform Random:** Random routing costs 57% more than Relay ($0.0185 vs $0.0118) for essentially the same quality.

---

## 7. Design Decisions & Trade-Offs

### Why Thompson Sampling?
Unlike greedy $\epsilon$-greedy heuristics, Thompson Sampling naturally incorporates **Bayesian posterior uncertainty**. In early phases (or under low evidence), wide probability distributions encourage principled exploration. As empirical evidence accumulates, sampling concentrates rapidly around the cheapest acceptable tier. Furthermore, integrating the cost penalty directly into the sampled score balances quality against token spend cleanly.

### Why a Transactional Outbox for Feedback?
Updating Beta posteriors in a direct web request creates a classic dual-write race condition and risks blocking user responses under SQLite lock contention. With a Transactional Outbox, the feedback record and an outbox event are committed in **one single SQLite transaction** (< 2ms). An asynchronous background worker applies decay and updates arms with exponential backoff retries. Events that fail 5 consecutive times automatically migrate to the `dead_letter` table for inspection.

### Why Fail-Open Redis?
Availability is paramount. If Redis experiences a crash, network partition, or OOM, the router automatically fails open:
- Rate limiting transitions transparently to an in-memory token bucket.
- Caching is temporarily bypassed (cache misses).
- Requests route normally without raising HTTP 500 errors.

---

## 8. Assumptions & Limitations

### Assumptions
1. **Token Cost Representation:** Relative tier cost in Thompson Sampling is normalized against representative output token pricing from Google AI Studio.
2. **Offline Fallback:** When `GEMINI_API_KEY` is not provided, Relay automatically switches to `MockProvider`, guaranteeing 100% offline testability and local development without cloud credentials.
3. **Idempotency Window:** Idempotency keys are cached for 24 hours, returning the exact historical payload without re-executing model calls.

### Limitations
1. **LLM Judge Bias:** When using `JUDGE_SAMPLE_RATE > 0` or building automated eval grades, the judge model (`gemini-2.5-pro`) may exhibit self-preference bias toward verbose or stylistic responses.
2. **Eval Dataset Scale:** The current benchmark suite utilizes 200 curated prompts. While stratified across 5 categories, larger enterprise deployments should expand this to 2,000+ domain-specific customer prompts.
3. **Provider Price Volatility:** API pricing changes over time. Always update `TIER_PRICING` in `app/config.py` to match current provider rates.
4. **Simulated Ground Truth:** Simulated benchmark mode demonstrates Bayesian convergence speed and theoretical properties; real-world routing efficacy should be validated on the `/ops` and `/learning` dashboards using live human feedback.

---

## 9. Quickstart Guide

### Option A: Docker Compose (Full Stack: API + Redis + Web)

1. Clone the repository and configure your environment:
```bash
git clone https://github.com/your-org/relay.git
cd relay
cp .env.example .env
# Edit .env and optionally add GEMINI_API_KEY=your_key
```

2. Start all services:
```bash
docker compose up --build
```

3. Access the services:
- **Web Dashboard:** [http://localhost:3000](http://localhost:3000)
- **FastAPI Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check:** [http://localhost:8000/healthz](http://localhost:8000/healthz)

---

### Option B: Local Development (Without Docker)

#### 1. Backend Setup
```bash
# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run linter and tests
ruff check .
pytest -v

# Start FastAPI server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000) to open the interactive Relay playground.

---

### Option C: Production Deployment (Vercel Frontend + Railway/Render Backend)

#### 1. Deploy Backend (Railway / Render / Fly.io)
Deploy the root repository using the included `Dockerfile` and `railway.json` or `render.yaml`:
- **Railway:** Connect this repo, add a Redis plugin, and set `GEMINI_API_KEY`.
- **Render:** Use the Blueprint (`render.yaml`) which automatically sets up Redis and the Docker web service with persistent disk.
- Note your live API URL (e.g. `https://relay-api.up.railway.app`).

#### 2. Deploy Frontend to Vercel
1. Log in to Vercel via CLI:
```bash
vercel login
```
2. Deploy the project:
```bash
vercel --prod
```
3. Set the environment variable in your Vercel Dashboard (or via CLI):
```bash
vercel env add NEXT_PUBLIC_API_URL
# Enter your hosted backend URL: https://relay-api.up.railway.app
```
