from typing import Dict, List, Optional


class CLOCritic:
    def __init__(self):
        self.iteration_count = 0
        self.max_iterations = 3

        # Pass memory: stores challenges raised in each prior pass so the Critic
        # can verify on the next pass whether the Analyst actually addressed them.
        self._prior_challenges: List[List[Dict]] = []
        # Stores the analyst's recommendations from prior passes to track responsiveness.
        self._prior_recommendations: List[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_assessment(self, analysis: Dict) -> Dict:
        """
        Main entry point to critique an analyst's assessment.
        On the first call this is a fresh evaluation.
        On subsequent calls the Critic first checks whether the challenges
        it previously raised have been addressed in the revised reasoning,
        then identifies any new gaps.
        """
        self.iteration_count += 1
        rec = analysis.get("recommendation", "HOLD")
        prior_rec = self._prior_recommendations[-1] if self._prior_recommendations else None

        # 1. Verify prior challenges BEFORE looking for new ones
        verification_results = self._verify_prior_challenges(analysis)

        # 2. Identify new / remaining gaps using heuristics
        raw_gaps = self.identify_gaps(analysis)

        # 3. Deduplicate raw gaps: do not raise gaps that are already raised in previous pass
        resolved_categories = {v["category"] for v in verification_results if v["resolved"]}
        unresolved_categories = {v["category"] for v in verification_results if not v["resolved"]}
        
        new_gaps = []
        for gap in raw_gaps:
            cat = gap.get("category")
            if cat in resolved_categories or cat in unresolved_categories:
                continue
            new_gaps.append(gap)

        # 4. Combine unresolved prior challenges (in gap format) and truly new gaps
        all_gaps = []
        for v in verification_results:
            if not v["resolved"]:
                orig = v.get("original_challenge") or {
                    "category": v.get("category"),
                    "problem": v.get("original_problem"),
                    "action": v.get("unresolved_action")
                }
                all_gaps.append(orig)
        all_gaps.extend(new_gaps)

        # 5. Recommendation responsiveness check
        rec_change_msg = ""
        rec_stubbornness_penalty = False
        rec_adaptability_reward = False
        
        if prior_rec:
            if prior_rec == rec:
                unresolved_gaps = [v for v in verification_results if not v["resolved"]]
                if unresolved_gaps:
                    rec_stubbornness_penalty = True
                    rec_change_msg = f"Analyst maintained recommendation '{rec}' despite {len(unresolved_gaps)} unresolved challenges."
                else:
                    rec_change_msg = f"Analyst maintained recommendation '{rec}' with all prior challenges addressed."
            else:
                rec_adaptability_reward = True
                rec_change_msg = f"Analyst adapted recommendation from '{prior_rec}' to '{rec}' based on critique."

        # 6. Framework traps check
        framework_critique = self.framework_check(analysis)

        # 7. Score using both penalties (gaps) and rewards (quality signals)
        score = self.calculate_score(
            analysis, 
            all_gaps, 
            verification_results,
            rec_stubbornness_penalty=rec_stubbornness_penalty,
            rec_adaptability_reward=rec_adaptability_reward
        )

        # 8. Decide: escalate if good enough or out of iterations
        decision = "LOOP BACK"
        if score >= 8 or self.iteration_count >= self.max_iterations:
            decision = "ESCALATE"
        elif score < 4:
            decision = "REJECT"

        # 9. Store the active gaps and recommendation so the NEXT pass can verify/track them
        self._prior_challenges.append(all_gaps)
        self._prior_recommendations.append(rec)

        return {
            "score": score,
            "decision": decision,
            "iteration": self.iteration_count,
            "challenges": all_gaps,
            "verification": verification_results,   # surface to dashboard logs
            "framework_critique": framework_critique,
            "alternative_view": self.generate_alternative_view(analysis),
            "recommendation_history": list(self._prior_recommendations),
            "recommendation_change_message": rec_change_msg
        }

    def reset(self):
        """Reset state between independent analysis sessions."""
        self.iteration_count = 0
        self._prior_challenges = []
        self._prior_recommendations = []

    # ------------------------------------------------------------------
    # Challenge verification (the core new capability)
    # ------------------------------------------------------------------

    def _verify_prior_challenges(self, analysis: Dict) -> List[Dict]:
        """
        For each challenge raised in the *most recent* prior pass, check
        whether the Analyst's updated reasoning now contains a substantive
        response.  Returns a list of dicts with 'resolved' bool and evidence.
        """
        if not self._prior_challenges:
            return []  # First pass — nothing to verify

        last_challenges = self._prior_challenges[-1]
        reasoning = analysis.get("reasoning", "")
        structural_insights = analysis.get("structural_insights", "")
        
        verification_results = []

        for challenge in last_challenges:
            category = challenge.get("category", "Unverified")
            problem = challenge.get("problem", "").lower()
            action = challenge.get("action", "").lower()

            # Find the specific block where the analyst formulated a response to this category
            response_block = ""
            marker = f"[critic challenge addressed — {category.lower()}]:"
            r_lower = reasoning.lower()
            if marker in r_lower:
                start_idx = r_lower.find(marker) + len(marker)
                next_marker_idx = r_lower.find("[", start_idx)
                if next_marker_idx != -1:
                    response_block = reasoning[start_idx:next_marker_idx].strip()
                else:
                    response_block = reasoning[start_idx:].strip()

            # Check if it was explicitly flagged as unresolved in structural insights
            unresolved_marker = f"[unresolved critic challenge — {category.lower()}]:"
            s_lower = structural_insights.lower()
            is_explicitly_unresolved = unresolved_marker in s_lower

            # Substantive check on response content using evidence keywords
            if response_block and not is_explicitly_unresolved:
                evidence_keywords = self._extract_evidence_keywords(problem, action)
                matches = [kw for kw in evidence_keywords if kw in response_block.lower()]
                resolved = len(matches) >= 1
            else:
                resolved = False
                matches = []

            verification_results.append({
                "category": category,
                "original_problem": challenge.get("problem", ""),
                "resolved": resolved,
                "evidence_found": matches if resolved else [],
                "unresolved_action": challenge.get("action", "") if not resolved else "",
                "original_challenge": challenge  # Store object reference for deduplication
            })

        return verification_results

    def _extract_evidence_keywords(self, problem: str, action: str) -> List[str]:
        """
        Derives a list of keywords from the challenge problem + action text
        that would indicate a genuine response. Uses a domain-specific mapping
        first; falls back to extracting multi-word nouns from the action string.
        """
        DOMAIN_MAP = {
            "pricing technicals": ["mvoc", "overcollateral", "technical demand", "demand shift", "collateral metric"],
            "single pricing point": ["distribution", "historic", "historical", "tier 1", "tier 2", "comparable", "comparison"],
            "execution slippage": ["slippage", "execution", "synchronized", "herd", "market impact"],
            "behavioral synchronization": ["synchronized", "synchronization", "herd", "correlated move"],
            "correlation": ["correlation", "cross-deal", "cross deal", "systemic"],
            "recovery": ["recovery", "lgd", "loss given default", "58%", "priming"],
            "lmt": ["lmt", "lme", "liability management", "priming", "uptiering"],
            "private credit": ["private credit", "direct lending", "mm clo", "credit estimate", "valuation lag"],
            "benchmark": ["benchmark", "historical norm", "legacy", "adjusted", "revised"],
            "stability": ["correlation", "stress test", "scenario", "cross-deal"],
        }

        keywords = []
        for key, values in DOMAIN_MAP.items():
            if key in problem or key in action:
                keywords.extend(values)

        # Fallback: pull significant tokens from the action string
        if not keywords:
            tokens = [w for w in action.split()
                      if len(w) > 4 and w not in {
                          "check", "verify", "compare", "ensure", "against",
                          "the", "and", "with", "from", "into", "that", "this",
                      }]
            keywords.extend(tokens[:4])

        return list(set(keywords))

    # ------------------------------------------------------------------
    # Gap identification (same focus areas, now cleaner)
    # ------------------------------------------------------------------

    def identify_gaps(self, analysis: Dict) -> List[Dict]:
        """
        Identifies logical gaps and missing data in the analysis.
        """
        gaps = []
        reasoning = analysis.get("reasoning", "").lower()
        structural = analysis.get("structural_insights", "").lower()
        combined = reasoning + " " + structural

        # Gap 1: Credit quality inferred purely from spread technicals
        if ("credit quality" in reasoning or "credit is stable" in reasoning) \
                and "spread" in reasoning \
                and "mvoc" not in combined \
                and "collateral" not in combined:
            gaps.append({
                "category": "Logical Gap",
                "problem": "Inferring credit quality from pricing technicals. "
                           "Spreads can stay tight due to demand even if fundamentals weaken.",
                "action": "Check actual collateral metrics: MVOC, defaults, CCC bucket concentration.",
            })

        # Gap 2: Single data-point anchoring
        key_facts = analysis.get("key_facts", {})
        if isinstance(key_facts, dict) and len(key_facts) < 2:
            gaps.append({
                "category": "Missing Data",
                "problem": "Analysis relies on a single pricing data point.",
                "action": "Compare against the last 5–10 Tier 1/2 pricing events "
                          "to establish a spread distribution and confirm value.",
            })
        elif isinstance(key_facts, list) and len(key_facts) < 2:
            gaps.append({
                "category": "Missing Data",
                "problem": "Analysis relies on a single pricing data point.",
                "action": "Compare against the last 5–10 Tier 1/2 pricing events "
                          "to establish a spread distribution and confirm value.",
            })

        # Gap 3: Recommending action during volatility without addressing execution risk
        if analysis.get("recommendation") in ("BUY", "SELL") \
                and "volatility" in combined \
                and "slippage" not in combined \
                and "synchronized" not in combined:
            gaps.append({
                "category": "Second-Order Effects",
                "problem": "Recommending action during high volatility without addressing "
                           "execution slippage or behavioral synchronization risk.",
                "action": "Evaluate whether acting now aligns with a 'synchronized' herd move "
                          "that may reverse once market impact is absorbed.",
            })

        # Gap 4: LMT / recovery rate blind spot
        if ("recovery" in combined and "58" not in combined and "lgd" not in combined) \
                or ("first-lien" in combined and "priming" not in combined):
            gaps.append({
                "category": "LGD Framework Gap",
                "problem": "Recovery assumptions may rely on legacy 70% LGD model rather than "
                           "the compressed ~58% European first-lien reality.",
                "action": "Stress-test recommendation against 58% recovery. "
                          "Flag any LMT/priming exposure in the underlying collateral pool.",
            })

        # Gap 5: Private credit valuation smoothing
        if ("private credit" in combined or "direct lending" in combined) \
                and "valuation" not in combined \
                and "credit estimate" not in combined:
            gaps.append({
                "category": "Private Credit Opacity",
                "problem": "Private credit / MM CLO signal without addressing quarterly "
                           "valuation lag and trigger cliff risk.",
                "action": "Apply a valuation haircut scenario and model the abrupt OC test "
                          "failure that occurs when delayed write-downs are forced.",
            })

        return gaps

    # ------------------------------------------------------------------
    # Framework trap check
    # ------------------------------------------------------------------

    def framework_check(self, analysis: Dict) -> Dict:
        """
        Checks for legacy framework traps (your thesis on structural blind spots).
        """
        traps = []
        text = (analysis.get("reasoning", "") + " " +
                analysis.get("structural_insights", "")).lower()

        if "benchmark" in text and "adjusted" not in text and "revised" not in text:
            traps.append(
                "Relying on historical benchmarks without adjustment for "
                "AI-speed market dynamics and compressed liquidity windows."
            )

        if "stable" in text and "correlation" not in text and "stress" not in text:
            traps.append(
                "Assuming stability without testing for cross-deal correlation spikes "
                "that manifest during synchronized sell-offs."
            )

        if "recovery" in text and "58" not in text and "70" not in text:
            traps.append(
                "Recovery rate referenced but not explicitly quantified — "
                "risk of defaulting to the obsolete 70% assumption."
            )

        return {
            "traps_identified": traps,
            "concern": (
                "Analysis relies on legacy operating assumptions that may not hold "
                "in current distressed credit environment."
                if traps else
                "No immediate legacy framework traps detected."
            ),
        }

    # ------------------------------------------------------------------
    # Scoring: positive criteria + penalties
    # ------------------------------------------------------------------

    def calculate_score(
        self,
        analysis: Dict,
        all_gaps: List[Dict],
        verification_results: List[Dict],
        rec_stubbornness_penalty: bool = False,
        rec_adaptability_reward: bool = False,
    ) -> int:
        """
        Score from 1–10.
        Base: 5.  Reward quality signals.  Penalise active gaps and stubbornness.
        """
        score = 5  # neutral baseline

        # Positive rewards
        reasoning = analysis.get("reasoning", "")
        key_facts = analysis.get("key_facts", {})

        if key_facts and len(key_facts) >= 2:
            score += 1   # multiple data points
        if analysis.get("structural_insights"):
            score += 1   # structural insight present
        if analysis.get("exposure"):
            score += 1   # portfolio exposure cross-check performed
        if analysis.get("conviction_pct", 0) >= 75:
            score += 1   # high conviction, well-reasoned
        if len(reasoning) > 150:
            score += 1   # substantive reasoning (not a one-liner)

        # Penalties: active gaps (which includes unresolved prior challenges + new gaps)
        # Deduct 2 points for each active challenge
        score -= len(all_gaps) * 2

        # Bonus: prior challenges that WERE resolved
        resolved = [r for r in verification_results if r["resolved"]]
        score += len(resolved)

        # Penalties/Rewards based on recommendation memory
        if rec_stubbornness_penalty:
            score -= 2   # Penalize maintaining a recommendation despite unresolved gaps
        if rec_adaptability_reward:
            score += 1   # Reward adapting the recommendation based on critique

        return max(1, min(10, score))

    # ------------------------------------------------------------------
    # Alternative view (devil's advocate)
    # ------------------------------------------------------------------

    def generate_alternative_view(self, analysis: Dict) -> str:
        """
        Generates a devil's advocate counter-thesis.
        """
        rec = analysis.get("recommendation", "HOLD")
        conviction = analysis.get("conviction_pct", 70.0)

        if rec == "BUY":
            if conviction < 60:
                return (
                    "Low-conviction BUY: the 'value' identified may be a value trap. "
                    "Wide spreads might reflect information asymmetry — "
                    "e.g., upcoming sector-specific downgrades not yet in public ratings."
                )
            return (
                "The 'Value' identified may be structural illiquidity premium, not mispricing. "
                "If current spreads are wide due to a thin buyer base, tightening may require "
                "a catalyst (new ETF inflows, CLO reset wave) that may not materialise on your timeline."
            )
        elif rec == "SELL":
            return (
                "Selling now may be premature. Technical demand from new CLO ETFs and "
                "insurance mandates could keep spreads tight for longer than fundamental "
                "metrics suggest. Evaluate the counter-party's motivation for selling first."
            )
        elif rec == "ESCALATE":
            return (
                "Escalating on direct exposure may overshoot. Confirm whether the news event "
                "is idiosyncratic to one deal or systemic across the manager's book before "
                "triggering a full portfolio review."
            )
        else:  # HOLD
            return (
                "A passive 'HOLD' might miss a first-mover advantage if this signal marks the "
                "start of a structural shift (e.g., macro-driven credit tightening or a new "
                "regulatory capital rule). Set a price trigger for re-evaluation."
            )
