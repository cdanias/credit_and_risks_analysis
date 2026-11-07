---
description: "Generates a personal 'MEM-JOG' Data Artefact (DC: 🐻 Bear stamped) to record an agent's achievement of expertise for reflection and recall after a substantial discovery session."
---

# Create MEM-JOG Workflow
**Description:** Generates a personal 'MEM-JOG' Data Artefact (DC: 🐻 Bear stamped) to record an agent's achievement of expertise for reflection and recall after a substantial discovery session. **STRICT ENFORCEMENT:** Agents are strictly prohibited from creating MEM-JOG documents outside of this workflow. A MEM-JOG MUST carry the Bear (🐻) DC classification and MUST be saved in the agent's personal `.agent\skills\<agent-name>\` directory. Creation in generic DOCS/ or workspace root directories is a Genetic Violation.

## Triggers
- The Agent Manager explicitly requests the agent to generate a MEM-JOG.
- A session meets a threshold criteria of significant architectural or technical discovery, and the Agent Manager approves a MEM-JOG creation.

## Process

### Step 1: Locate the Template
The baseline template for MEM-JOGs is stored at:
`.agent\skills\mission-critical-java-payments\MEM-JOG-TEMPLATE.md`

### Step 2: Create the Agent's Personal MEM-JOG
The agent must read the template and create a new markdown file in their own personal skill directory. The file name MUST be prefixed with a date and time stamp (`YYMMDDHHMM`).
> **Timestamp Derivation:** Agents MUST run `python roc/scripts/look_at_watch.py` to retrieve the deterministic OS timestamp. Never invent or hallucinate the timestamp.
**Target Path:** `.agent\skills\<current-agent-skill-folder>\MEM-JOG-<YYMMDDHHMM>-<Topic-Name>.md`

*Note: If the agent does not have a dedicated folder, the Agent Manager should be consulted on where to store the file.*

### Step 3: Populate the Content
The agent must populate the sections defined in the template:
1. **Header Metadata**: Fill in `Author`, `Version`, `Last_Updated`, session context, and importantly, the `Service_Types_In_Scope` (e.g., T300, P150, O400). Ensure the `Classifier: 🐻` remains intact. This header format mirrors a RAD*ICAL code header.
2. **What**: Define the core problem, challenge, or discovery.
3. **Why**: Explain the business and architectural significance.
4. **How**: Detail the implementation specifics (e.g., registries, multi-modalities).
5. **Where**: List impacted files, ADRs, and MEMOs.
6. **Software Construction Standards Alignment**: Explicitly align the work to best practices (SOLID, DRY, abstraction, state management, resilience).
7. **Unknowns / Future Risk Factors**: Document unproven elements or ambiguities that might force a revision.
8. **Bibliography**: List referenced materials, NotebookLM bases, academic disciplines, or project artifacts.

### Step 4: Confirm with Agent Manager
Once the MEM-JOG is saved, the agent should output a confirmation message to the Agent Manager providing a link to the newly created `.md` file, using the signature `— <AGENT_NAME> logged this expertise for future recall.`
