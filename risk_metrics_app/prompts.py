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

    text_content = f"""Please analyze this {metric_name} risk metric chart and provide insights.

Statistical Summary:
- Mean: {stats['mean']:.4f}
- Median: {stats['median']:.4f}
- Standard Deviation: {stats['std']:.4f}
- Min: {stats['min']:.4f}
- Max: {stats['max']:.4f}
- Range: {stats['max'] - stats['min']:.4f}
- Data Points: {stats['count']}{outlier_info}{breach_info}

Please provide:
1. Overall trend analysis for the period shown
2. Volatility observations based on the standard deviation
3. Analysis of any outliers and what they might indicate
4. Assessment of limit breaches (if any) and their significance
5. Key insights about the risk metric's behavior
6. Risk implications and notable patterns

Keep the analysis concise but informative (3-4 paragraphs)."""

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

    prompt = f"""You are a risk analyst tasked with providing a comprehensive portfolio-level risk assessment based on individual risk metric analyses.

<analysis_data>
{all_metrics_xml}
</analysis_data>

Based on the above data for {len(metrics_analyses)} risk metric(s), please provide a comprehensive risk portfolio summary that includes:

1. **Overall Risk Profile**: Analyze the collective behavior of these risk metrics during the analyzed period. What is the overall risk exposure?

2. **Comparative Risk Assessment**: Compare and contrast the different risk metrics. Which metrics showed the highest volatility? Which are most concerning?

3. **Limit Breach Analysis**: Assess the significance of any limit breaches across metrics. Are there systematic issues or isolated incidents?

4. **Correlation and Dependencies**: Identify any potential correlations or dependencies between risk metrics that could indicate systemic risks.

5. **Key Risk Indicators**: Highlight the 3-5 most critical risk indicators that require immediate attention or monitoring.

6. **Risk Mitigation Recommendations**: Provide actionable insights for risk management and mitigation strategies.

Please structure your response in clear sections and keep it concise yet comprehensive (4-6 paragraphs total). Focus on synthesizing the information to provide strategic risk insights."""

    return prompt


__all__ = ["create_llm_prompt", "create_portfolio_summary_prompt"]
