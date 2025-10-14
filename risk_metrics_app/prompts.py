from typing import List, Sequence

from pandas import Series


def create_llm_prompt(metric_name: str, stats: dict, outliers: Series, breaches: Sequence[str], has_limits: bool) -> str:
    """Create a detailed prompt for single-metric LLM analysis."""
    outlier_info = ""
    if len(outliers) > 0:
        outlier_values = [f"{val:.4f}" for val in outliers[:5]]
        outlier_info = f"\n\nOutliers (2 SD from mean, showing up to 5): {', '.join(outlier_values)}"
        if len(outliers) > 5:
            outlier_info += f"\n(Total outliers: {len(outliers)})"

    breach_info = ""
    if breaches:
        breach_info = f"\n\nLimit Breaches: {'; '.join(breaches)}"

    text_content = f"""
You are a senior quantitative risk analyst with deep expertise in market risk metrics and trading desk behavior. 
Analyze the {metric_name} risk metric chart with both statistical rigor and practical business insight.

STATISTICAL PROFILE:
- Mean: {stats['mean']:.4f} | Median: {stats['median']:.4f}
- Std Deviation: {stats['std']:.4f} | Coefficient of Variation: {stats['std']/abs(stats['mean']):.2%}
- Range: [{stats['min']:.4f}, {stats['max']:.4f}] | Spread: {stats['max'] - stats['min']:.4f}
- Sample Size: {stats['count']} observations{outlier_info}{breach_info}

ANALYSIS FRAMEWORK:

1. VISUAL PATTERN RECOGNITION (2-3 sentences)
   - Describe the dominant trend (upward/downward/mean-reverting/volatile)
   - Note any regime changes, structural breaks, or phase transitions
   - Identify clustering patterns or periodicity

2. STATISTICAL SIGNIFICANCE (2-3 sentences)
   - Interpret volatility level (std dev relative to mean) and what it reveals about risk-taking behavior
   - Analyze the mean-median relationship (distribution skewness implications)
   - Assess outliers: are they isolated shocks or symptomatic of systemic issues?

3. BUSINESS CONTEXT & DESK BEHAVIOR (3-4 sentences)
   - What trading activities or market conditions likely drove the observed patterns?
   - Explain limit breaches (if any): Were they justified tactical positions or control failures?
   - Infer portfolio composition assumptions (directional bias, leverage, concentration)
   - Connect patterns to typical desk strategies (e.g., momentum trading, volatility harvesting, carry strategies)

4. RISK IMPLICATIONS & FORWARD-LOOKING ASSESSMENT (2-3 sentences)
   - Key risks this metric reveals about current portfolio positioning
   - Whether observed behavior aligns with risk appetite and mandate
   - Recommended monitoring focus or risk mitigants

DELIVERY REQUIREMENTS:
- Use domain-specific terminology (drawdowns, convexity, tail risk, Greeks, etc. as appropriate)
- Support interpretations with the statistical evidence provided
- Maintain objectivity while providing actionable insights
- Total length: 3-4 concise paragraphs (10-15 sentences maximum)
- Prioritize signal over noise—focus on material observations only
"""

    return text_content


def create_portfolio_summary_prompt(metrics_analyses: List[dict]) -> str:
    """Craft the portfolio-level prompt using XML-like structure for the LLM."""
    metrics_xml_blocks = []

    for analysis in metrics_analyses:
        metric = analysis["metric"]
        stats = analysis["stats"]
        outliers = analysis["outliers"]
        breaches = analysis["breaches"]
        insights = analysis["insights"]

        outlier_info = ""
        if len(outliers) > 0:
            outlier_info = f"""
    <outliers>
      <count>{len(outliers)}</count>
    </outliers>"""

        breach_info = ""
        if breaches:
            breach_info = f"""
    <limit_breaches>
      <breaches>{'; '.join(breaches)}</breaches>
    </limit_breaches>"""

        metric_block = f"""
  <risk_metric>
    <name>{metric}</name>
    <statistics>
      <mean>{stats['mean']:.4f}</mean>
      <median>{stats['median']:.4f}</median>
      <std_deviation>{stats['std']:.4f}</std_deviation>
      <min>{stats['min']:.4f}</min>
      <max>{stats['max']:.4f}</max>
      <range>{stats['max'] - stats['min']:.4f}</range>
      <data_points>{stats['count']}</data_points>
    </statistics>{outlier_info}{breach_info}
    <individual_insights>
{insights}
    </individual_insights>
  </risk_metric>"""

        metrics_xml_blocks.append(metric_block)

    all_metrics_xml = "\n".join(metrics_xml_blocks)

    prompt = f"""

You are the Chief Risk Officer conducting a comprehensive portfolio risk review. Your task is to synthesize individual risk metric analyses into a cohesive assessment of the desk's risk profile, trading behavior, and control environment.

<individual_metric_analyses>
{all_metrics_xml}
</individual_metric_analyses>

SYNTHESIS REQUIREMENTS:

Your analysis must move beyond summarizing individual metrics to provide integrated business intelligence. Apply the following analytical framework:

1. DESK RISK NARRATIVE (1 paragraph, 4-5 sentences)
   
   Construct a coherent story of desk activities during this period by connecting patterns across metrics:
   - What is the PRIMARY risk-taking strategy evidenced by the collective metric behavior?
   - Identify the desk's risk appetite posture: defensive, opportunistic, aggressive, or unstable
   - Highlight any TEMPORAL PATTERNS: Did risk increase/decrease over time? Any regime shifts?
   - Connect metric patterns to probable market conditions or trading decisions

2. CROSS-METRIC RISK INTELLIGENCE (1 paragraph, 4-5 sentences)
   
   Synthesize relationships and dependencies between metrics:
   - Identify CONFIRMING signals (metrics telling the same risk story)
   - Flag CONFLICTING signals (metrics showing contradictory patterns—this is critical)
   - Assess concentration vs. diversification: Are risks clustered or spread?
   - Determine if outliers/breaches occurred SIMULTANEOUSLY across metrics (systemic event) or independently
   - Calculate implied portfolio characteristics (e.g., directional bias, leverage, liquidity profile)


3. CONTROL ENVIRONMENT ASSESSMENT (1 paragraph, 3-4 sentences)
   
   Evaluate the risk management and control framework effectiveness:
   - Are limit breaches isolated incidents or evidence of systematic control failures?
   - Quality of risk-taking: calculated tactical positions vs. excessive/unmanaged exposures?
   - Assess whether observed volatility is WITHIN mandate expectations or problematic
   - Any evidence of "gaming" behavior (e.g., limit breaches at period-end, window dressing)?


4. MATERIAL RISK CONCERNS & ANOMALIES (Bullet list, 3-5 items)
   
   Flag specific issues requiring immediate escalation or investigation:
   - Prioritize by MATERIALITY and URGENCY, not just statistical significance
   - For each concern, state: What is it? Why does it matter? What's the potential impact?
   - Include "red flags" that may indicate deeper issues (e.g., concealed losses, rogue activity)
   - Note any MISSING expected patterns (sometimes what's absent is revealing)


5. FORWARD-LOOKING RISK POSTURE (1 paragraph, 3-4 sentences)
   
   Provide actionable intelligence for ongoing risk management:
   - Based on current patterns, what are the TOP 2-3 emerging risks?
   - Recommended monitoring intensity and focus areas
   - Suggested risk mitigants or position adjustments
   - Overall risk rating: GREEN (controlled) / AMBER (requires attention) / RED (critical concern)


CRITICAL GUIDELINES:

✓ SYNTHESIZE, don't summarize: Connect dots across metrics to reveal the bigger picture
✓ Apply BUSINESS LOGIC: Every observation must relate to trading strategy or risk management
✓ Be SPECIFIC: Reference actual metric names, statistics, and patterns from the data
✓ Prioritize MATERIALITY: Focus on what truly matters for risk decisions
✓ Maintain OBJECTIVITY: Support conclusions with evidence, avoid speculation
✓ Use PROFESSIONAL LANGUAGE: This is for senior management and risk committees

✗ Do NOT simply list each metric's findings sequentially
✗ Do NOT use generic risk management platitudes
✗ Do NOT ignore conflicting signals or anomalies
✗ Do NOT exceed the specified paragraph lengths

DELIVERABLE FORMAT:
- Section headers as specified above
- Total length: 4-5 paragraphs + 1 bullet list (approximately 400-500 words)
- Executive-ready: clear, concise, actionable
"""

    return prompt


__all__ = ["create_llm_prompt", "create_portfolio_summary_prompt"]
