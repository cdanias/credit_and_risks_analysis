# CLO Intelligence Pipeline

Autonomous system for monitoring, analyzing, and stress-testing the CLO (Collateralized Loan Obligation) market.

## Project Structure

- `src/agents/`: Core logic for AI agents (News Reader, Analyst, Critic).
- `.agent/`: High-level instructions and skills for AI agents.
- `docs/`: Technical documentation and architecture.
- `tests/`: Automated test suite.

## Getting Started

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run tests:
   ```bash
   pytest
   ```

## Agents

- **News Reader**: Fetches and parses market news.
- **Analyst**: Analyzes trends and pricing.
- **Critic**: Provides skeptical risk analysis and identifies structural flaws.
