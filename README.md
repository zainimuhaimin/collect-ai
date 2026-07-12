# 🚀 CollectAI Machine Learning System

**Advanced ML-powered recovery score prediction for debt collection management**

---

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Prerequisites](#-prerequisites)
- [Setup Guide](#-setup-guide)
- [Running the ML Pipeline](#-running-the-ml-pipeline)
- [System Architecture](#-system-architecture)

---

## ⚡ Quick Start

Get the system running in 5 minutes:

```bash
# 1. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
cd app/machine-learning
pip install -r requirements.txt

# 3. Setup database
psql -U postgres -f config/schema.sql

# 4. Generate sample data
python ../../faker/generate-faker-realistic.py

# 5. Train initial model
python pipelines/train_initial_model.py

# 6. Run daily scoring
python pipelines/daily_scoring.py
```

---

## 📦 Prerequisites

### System Requirements
- **Python**: 3.9+ (tested on 3.9.6)
- **PostgreSQL**: 12+ (with psycopg2 driver)
- **macOS**: libomp (OpenMP runtime for XGBoost)
  ```bash
  brew install libomp
  ```

### Python Packages
All dependencies specified in `app/machine-learning/requirements.txt`:
- XGBoost 2.1.4 (gradient boosting model)
- scikit-learn 1.6.1 (ML utilities)
- pandas 2.3.3 (data manipulation)
- SQLAlchemy 2.0.51 (database ORM)
- psycopg2-binary 2.9.12 (PostgreSQL adapter)

---

## 🔧 Setup Guide

### Step 1️⃣: Create Virtual Environment

```bash
cd /path/to/collect-ai
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# or: .venv\Scripts\activate  # Windows
```

### Step 2️⃣: Install Dependencies

```bash
cd app/machine-learning
pip install --upgrade pip
pip install -r requirements.txt
```

**Verification:**
```bash
python -c "import xgboost, sklearn, pandas, sqlalchemy; print('✓ All packages imported successfully')"
```

### Step 3️⃣: Create Database Schema

Initialize PostgreSQL database with CollectAI schema:

```bash
psql -U postgres -d collect_ai -f config/schema.sql
```

**Tables created:**
- `customer_master` — Customer demographics & risk profile
- `contract_snapshot` — Active loan contracts
- `payment_history` — Monthly payment records
- `lkp_interaction` — Collection interaction logs
- `customer_behavioral_standing` — CBS profile per customer
- `ai_intelligence_output` — Daily scoring results

**Verify setup:**
```bash
psql -U postgres -d collect_ai -c "\dt"
```

### Step 4️⃣: Generate Sample Data

Generate realistic synthetic data using Faker:

```bash
cd ../../faker
python generate-faker-realistic.py
```

**What this does:**
- Generates 100 customers with realistic demographics
- Creates 150-200 contracts with income-based risk profiles
- Simulates 18 months of payment history
- Includes collection interaction logs
- Ensures 35-40% paid rate (realistic default distribution)
- Populates all 4 input tables

**Expected output:**
```
Mulai menghasilkan data dummy...
Generated 100 customers
Generated 180 contracts (avg 1.8 per customer)
Generated 720 payment records
Generated 85 collection interactions
Saving to Excel: Dataset_CollectAI_Dummy.xlsx
Exporting to PostgreSQL... ✓ Success
```

---

## 🎯 Running the ML Pipeline

### Step 5️⃣: Train Initial Recovery Model

Build the champion model using training data:

```bash
cd ../app/machine-learning
python pipelines/train_initial_model.py
```

**What this pipeline does:**

| Stage | Action | Output |
|-------|--------|--------|
| **Feature Engineering** | Extract 20+ features from 4 source tables | `contract_features.pkl` |
| **CBS Building** | Compute Customer Behavioral Standing grades | Updates `customer_behavioral_standing` |
| **Outcome Labeling** | Build target variable (paid/unpaid) | Training dataset n=150 |
| **Model Training** | Train XGBoost with recency-weighted strategy | Precision, Recall, AUC metrics |
| **Model Registration** | Version and register champion model | `models/recovery_model_champion.pkl` |

**Expected output:**
```
[Labeler] training: n=150, paid=55 (36.7%), unpaid=95
[Model] Training with strategy: recency_weighted (decay_rate=0.70)
[Model] Cross-validation AUC: 0.68 (+/- 0.08)
[Model] Top features: ptp_reliability_index, delay_trend, payment_rate
[Registry] Model registered as champion v3
✓ Model saved: models/recovery_model_champion.pkl
```

**Model artifact details:**
- **Location**: `models/recovery_model_champion.pkl`
- **Version**: Tracked in `models/registry.json`
- **AUC Threshold**: MIN_CV_AUC_TO_DEPLOY = 0.50 (configurable via env var)

### Step 6️⃣: Run Daily Scoring Pipeline

Score all active contracts and publish results:

```bash
python pipelines/daily_scoring.py
```

**What this pipeline does:**

| Stage | Action | Output |
|-------|--------|--------|
| **Load Data** | Fetch all active contracts from DB | n=180 contracts |
| **Feature Extraction** | Compute real-time features for scoring | 20 features per contract |
| **Model Scoring** | Apply champion model to generate RECOVERY_SCORE | Probability 0.0-1.0 |
| **Confidence Level** | Compute confidence score (data quality, history depth, model certainty) | CONFIDENCE_LEVEL 0.0-1.0 |
| **Business Rules** | Apply decision logic (segmentation, NBA, priority) | RISK_SEGMENT, CHANNEL, PRIORITY |
| **Quality Checks** | Validate output integrity & distribution | Hard & soft checks |
| **Publish Results** | Insert scoring output to `ai_intelligence_output` table | Daily snapshot |

**Expected output:**
```
[Daily Scoring] Loading contracts...
[Daily Scoring] CBS bootstrap: 50 records
[Daily Scoring] Scoring 180 contracts...

[QC] Summary
  - range_score_confidence   [hard] PASS
  - null_required            [hard] PASS
  - duplicate_contract_no    [hard] PASS
  - wont_pay_pct<=30%        [soft] PASS
  - cust_exists_in_cbs       [soft] PASS

✓ [Daily Scoring] Success
  Contracts scored: 180
  Segment breakdown: {'Can Pay': 95, 'Cannot Pay': 55, 'Won't Pay': 28, 'Self-cure': 2}
  Priority breakdown: {'Critical': 8, 'High': 42, 'Medium': 85, 'Low': 45}
```

**Output stored in:**
- Database table: `ai_intelligence_output`
- Columns: `contract_no`, `recovery_score`, `confidence_level`, `risk_segment`, `nba_recommendation`, `priority_level`, `scoring_date`

---

## 🏗️ System Architecture

### Data Flow
```
┌──────────────────┐
│   4 Input Tables │
│  (customer_*,    │
│   contract_*,    │
│   payment_*,     │
│   lkp_*)         │
└────────┬─────────┘
         │
         ▼
┌──────────────────────┐
│ Feature Engineering  │ ← 20 features per contract
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ CBS Building         │ ← Customer Behavioral Standing
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ Model Scoring        │ ← XGBoost Champion
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ Business Rules       │ ← Segmentation, NBA, Priority
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ Quality Checks       │ ← Validation & Distribution
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ ai_intelligence_     │ ← Daily Output
│ output (Published)   │
└──────────────────────┘
```

### Key Components

**Training Pipeline** (`pipelines/train_initial_model.py`)
- Loads historical data
- Builds features & CBS
- Trains XGBoost model
- Registers model version

**Daily Scoring Pipeline** (`pipelines/daily_scoring.py`)
- Scores all active contracts
- Applies business rules
- Validates output quality
- Publishes results daily

**Model Registry** (`src/model_registry.py`)
- Version tracking (champion/challenger)
- Performance history
- Rollback capability

**Monitoring & MLOps** (Phase 6 - in development)
- Model drift detection
- Champion-challenger evaluation
- Weekly retraining orchestration

---

## 📊 Sample Queries

### View Scoring Results
```sql
SELECT contract_no, recovery_score, risk_segment, priority_level, scoring_date
FROM ai_intelligence_output
WHERE scoring_date = CURRENT_DATE
ORDER BY recovery_score DESC
LIMIT 10;
```

### Check Model History
```sql
SELECT version, auc, trained_date, status
FROM ai_model_registry
ORDER BY trained_date DESC;
```

### Customer Profile
```sql
SELECT cust_id, behavioral_grade, recovery_effort_level, b_list_status
FROM customer_behavioral_standing
LIMIT 5;
```

---

## ⚙️ Configuration

### Environment Variables

```bash
# Model training threshold (default: 0.50)
export COLLECTAI_MIN_CV_AUC_TO_DEPLOY=0.50

# Database connection (if not using config/settings.py)
export DATABASE_URL="postgresql://user:password@localhost/collect_ai"
```

### Settings File
Edit `config/settings.py` to customize:
- Feature columns
- Model hyperparameters
- Decision thresholds
- CBS rules

---

## 🆘 Troubleshooting

### Issue: "libomp.dylib not found" (macOS)
```bash
brew install libomp
```

### Issue: "Module 'xgboost' not found"
```bash
pip install --upgrade xgboost scikit-learn
```

### Issue: "Connection to database refused"
Check PostgreSQL is running:
```bash
psql -U postgres -c "SELECT 1;"
```

### Issue: "AUC below threshold (0.50)"
- Add more training data (need minimum 500 samples for better signal)
- Check data quality in `payment_history` table
- Verify outcome labeling in `outcome_labeler.py`

---

## 📈 Next Steps

### Phase 6: MLOps & Monitoring
- [ ] Implement model drift detection
- [ ] Setup champion-challenger framework
- [ ] Create weekly retraining orchestrator

### Phase 7: Production Deployment
- [ ] Write integration tests
- [ ] Setup Airflow/cron scheduling
- [ ] Create production README & deployment guide

---

## 📝 License & Contact

CollectAI - Advanced ML-powered Recovery Score Prediction System

For questions or issues, refer to the documentation files:
- [System Rules](rules-engine.md)
- [ML Ops Pipeline](ml-ops-pipeline.md)
- [Scoring Engine](scoring-engine.md)
- [Flow & Rules](flow-and-rules.md)

