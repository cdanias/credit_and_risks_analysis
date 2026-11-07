---
name: clo-pipeline
description: Full CLO monitoring pipeline - searches news, analyzes impact, critiques reasoning, and loops until analysis is solid or max iterations reached.
---

# CLO Market Intelligence Pipeline

This workflow orchestrates the full CLO analysis pipeline: Reader → Analyst → Critic → (loop or escalate).

## Workflow Trigger

To run this workflow, the user types:
/clo-pipeline

Or:
Run the CLO pipeline

## Workflow Steps

### STEP 1: NEWS COLLECTION
**Agent:** CLO News Reader
**Task:** Find CLO news from the past week
**Output:** Structured news data with signals

**Instructions to Reader:**
Find CLO news from the past 7 days. Focus on:

Issuance and pricing
Spread movements
Manager announcements
Credit events

Format output as structured data for the Analyst.

**Success criteria:** At least 1 relevant article found
**Failure handling:** If no news found, report to user and end workflow

---

### STEP 2: ANALYSIS
**Agent:** CLO Analyst
**Task:** Analyze the news signals from Step 1
**Input:** News data from Reader
**Output:** Full assessment with recommendations

**Instructions to Analyst:**
Analyze the CLO news signals from the Reader.
For each signal, provide:

Credit quality impact
Pricing implications
Portfolio positioning recommendations
Structural risk assessment

Output your full analysis in the standard format.

**Success criteria:** Analysis completed with clear recommendation
**Failure handling:** If analysis cannot be completed (missing critical data), escalate to user

---

### STEP 3: CRITIQUE (Iteration Loop)
**Agent:** CLO Critic
**Task:** Challenge the Analyst's reasoning
**Input:** Analysis from Step 2
**Output:** Quality score + gaps identified + decision (LOOP/ESCALATE/REJECT)

**Instructions to Critic:**
Review the CLO Analyst's assessment.
Identify:

Logical gaps
Missing data
Untested assumptions
Alternative interpretations
Framework concerns

Score the analysis (1-10) and decide:

LOOP BACK (5-7/10) if gaps can be addressed
ESCALATE (8-10/10) if analysis is solid
REJECT (1-4/10) if fundamentally flawed

Current iteration: [TRACK THIS]
Max iterations: 3

**Success criteria:** Clear decision made (LOOP/ESCALATE/REJECT)

---

### STEP 4: DECISION LOGIC

**IF Critic says LOOP BACK:**
- Increment iteration counter
- IF iteration < 3:
  - Pass critique back to Analyst (return to Step 2)
  - Analyst addresses gaps and produces updated analysis
  - Go to Step 3 (Critic reviews again)
- IF iteration = 3:
  - Force ESCALATE (prevent infinite loop)
  - Go to Step 5

**IF Critic says ESCALATE:**
- Go to Step 5 (present to user)

**IF Critic says REJECT:**
- Flag critical failure
- Present Analyst's analysis + Critic's rejection to user
- User decides: retry from scratch or abandon

---

### STEP 5: PRESENTATION TO USER

**Agent:** Workflow Manager (this workflow itself)
**Task:** Present final results to Χρήστος

**Output format:**
═══════════════════════════════════════════
CLO PIPELINE RESULTS
═══════════════════════════════════════════
STATUS: [COMPLETED | REJECTED]
ITERATIONS: [X]/3
───────────────────────────────────────────
NEWS SIGNALS FOUND
───────────────────────────────────────────
[Summary of articles from Reader]
[Number of articles: X]
[Signal types: issuance (X), spreads (X), credit events (X)]
───────────────────────────────────────────
ANALYST ASSESSMENT
───────────────────────────────────────────
[Final analysis after all iterations]
Recommendation: [BUY | SELL | HOLD | ESCALATE]
Confidence: [Based on Critic score]
───────────────────────────────────────────
CRITIC REVIEW
───────────────────────────────────────────
Quality Score: [X]/10
Status: [APPROVED | NEEDS ATTENTION]
[If gaps remain, list them]
───────────────────────────────────────────
ITERATION HISTORY
───────────────────────────────────────────
Iteration 1:

Gaps identified: [X]
Analyst response: [Summary]

[Iteration 2, 3 if applicable...]
───────────────────────────────────────────
RECOMMENDATION FOR ΧΡΉΣΤΟΣ
───────────────────────────────────────────
[Clear action item based on final analysis]
[If framework concerns flagged, highlight them here]
═══════════════════════════════════════════

---

## Error Handling

**If Reader finds no news:**
→ Report to user: "No significant CLO news in past 7 days. Extend search window? (Y/N)"

**If Analyst cannot complete analysis:**
→ Report missing data, ask user to provide or abort

**If Critic rejects after 3 iterations:**
→ Present both Analyst and Critic views, let user decide

**If workflow stalls (agent doesn't respond):**
→ Timeout after 5 minutes, report to user

---

## State Management

**Track these variables:**
iteration_count = 0
max_iterations = 3
news_data = null
analysis_data = null
critique_data = null
status = "running" | "completed" | "failed"

---

## Usage Example

**User types:**
/clo-pipeline

**Workflow executes:**
1. Reader searches web → finds 6 articles
2. Analyst analyzes → produces assessment (BUY recommendation)
3. Critic reviews → finds 2 gaps, scores 6/10, says LOOP BACK
4. Analyst addresses gaps → updated assessment
5. Critic reviews again → scores 8/10, says ESCALATE
6. Workflow presents final results to user

**Total time:** 3-5 minutes
**User intervention:** None (fully autonomous)

---

## Advanced: Scheduling (Future Enhancement)

Once this works, you could add:
Run /clo-pipeline every Monday at 9am Athens time

This would give you a weekly CLO intelligence briefing automatically.

---

## Customization Options

User can modify workflow behavior:
/clo-pipeline --depth=deep    (searches 14 days instead of 7)
/clo-pipeline --focus=spreads (only spread-related news)
/clo-pipeline --fast          (max 1 iteration, accept imperfect analysis)

