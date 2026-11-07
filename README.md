# CLO Intelligence Pipeline

Autonomous system for monitoring, analyzing, and stress-testing the CLO (Collateralized Loan Obligation) market.

## Project Structure

- `.agent/skills/`: Antigravity agent skills (`clo-news-reader`, `clo-analyst`, `clo-critic`, `clo-pipeline`).
- `src/agents/`: Core Python logic for AI agents (`news_reader`, `analyst`, `critic`) and pipeline runners.
- `backend/`: FastAPI server (`main.py`) and risk calculation engine (`risk_engine/`).
- `frontend/`: Interactive HTML dashboards (`clo-analyst-dashboard.html`, `surveillance_dashboard.html`).
- `docs/`: Architecture, credit risk research, and analysis reports.
- `scripts/`: Utility scripts (`save-to-github.sh`).
- `tests/`: Automated pytest suite.

## Getting Started

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run tests:
   ```bash
   pytest
   ```
3. Start the Backend API & Dashboard Server:
   ```bash
   python backend/main.py
   ```
   - Analyst Dashboard: `http://localhost:8000/`
   - Surveillance Dashboard: `http://localhost:8000/surveillance`

## Agents & Skills

- **CLO News Reader**: Fetches and parses market news and structured credit signals.
- **CLO Analyst**: Maps market signals to bond positioning and credit impact assessments.
- **CLO Critic**: Adversarial challenger that stress-tests Analyst reasoning and flags structural flaws.
- **CLO Pipeline (`/clo-pipeline`)**: End-to-end iterative workflow across Reader → Analyst → Critic.
