from datetime import datetime
from io import BytesIO
from typing import Dict, List, Optional, Tuple
import zipfile
import re

import plotly.io as pio

from .metrics import PRIORITY_METRICS, parse_metric_name, get_maturity_order
from .visuals import create_limit_annotation_html


def metric_status(analysis: dict) -> str:
    """Return 'breach', 'outlier', or 'ok' for a metric analysis.

    Precedence: a breaching metric is 'breach' even if it also has outliers.
    """
    if analysis.get("breaches"):
        return "breach"
    if len(analysis.get("outliers", [])) > 0:
        return "outlier"
    return "ok"


def kpi_counts(metrics_analyses: List[dict]) -> dict:
    """Aggregate status counts for the KPI summary strip."""
    counts = {"total": len(metrics_analyses), "breach": 0, "outlier": 0, "ok": 0}
    for analysis in metrics_analyses:
        counts[metric_status(analysis)] += 1
    return counts


def make_anchor_id(metric: str) -> str:
    """
    Generate a safe HTML anchor ID from a metric name.
    
    This function ensures valid HTML IDs by converting metric names to lowercase,
    replacing special characters (including brackets, spaces, slashes) with dashes,
    and adding a "metric-" prefix to avoid collisions and ensure IDs don't start with numbers.
    
    Args:
        metric: The metric name which may contain special characters
        
    Returns:
        A valid HTML anchor ID string
    
    Examples:
        "VaR" -> "metric-var"
        "BasisSensiByCurrencyByPillar[EUR][1W]" -> "metric-basissensibycurrencybypillar-eur-1w"
    """
    # Convert to lowercase
    anchor = metric.lower()
    # Replace non-alphanumeric characters with dash
    anchor = re.sub(r'[^a-z0-9]+', '-', anchor)
    # Collapse repeated dashes
    anchor = re.sub(r'-+', '-', anchor)
    # Trim leading/trailing dashes
    anchor = anchor.strip('-')
    # Prefix to avoid collisions and ensure valid ID
    return f"metric-{anchor}"


def sanitize_node_name(node_name: str) -> str:
    """Sanitize a node name for safe use in file paths and folder names.
    
    Replaces characters that are invalid in file system paths with underscores
    and trims whitespace.
    
    Args:
        node_name: The original node name from the data.
        
    Returns:
        A sanitized string safe for use in file paths.
        
    Examples:
        "Node/A" -> "Node_A"
        "Node: Test" -> "Node_ Test"
        "  spaces  " -> "spaces"
    """
    # Replace characters invalid in Windows/Unix file paths
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', node_name)
    # Trim whitespace
    sanitized = sanitized.strip()
    # Ensure non-empty
    return sanitized if sanitized else "unnamed_node"


def _sort_metrics_by_priority(metrics_analyses: List[dict]) -> List[dict]:
    """Sort metrics analyses by priority (VaR, SVaR, STTHH first) then by name and maturity.
    
    This ensures the HTML report displays priority risk metrics at the top,
    followed by other metrics sorted alphabetically with maturity ordering.
    
    Args:
        metrics_analyses: List of metric analysis dictionaries with 'metric' key.
        
    Returns:
        Sorted list of metric analyses.
    """
    # Separate priority metrics from others
    priority_analyses = []
    other_analyses = []
    
    for analysis in metrics_analyses:
        metric = analysis["metric"]
        metric_lower = metric.lower()
        is_priority = any(pm.lower() == metric_lower for pm in PRIORITY_METRICS)
        if is_priority:
            priority_analyses.append(analysis)
        else:
            other_analyses.append(analysis)
    
    # Sort priority metrics in defined order
    def priority_sort_key(analysis: dict) -> int:
        metric_lower = analysis["metric"].lower()
        for idx, pm in enumerate(PRIORITY_METRICS):
            if pm.lower() == metric_lower:
                return idx
        return len(PRIORITY_METRICS)
    
    priority_analyses.sort(key=priority_sort_key)
    
    # Sort other metrics by base name, then maturity
    def other_sort_key(analysis: dict) -> Tuple[str, int, int, str]:
        metric = analysis["metric"]
        base_name, maturity = parse_metric_name(metric)
        maturity_order = get_maturity_order(maturity)
        maturity_flag = 0 if maturity is None else 1
        return (base_name.lower(), maturity_flag, maturity_order, metric)
    
    other_analyses.sort(key=other_sort_key)
    
    return priority_analyses + other_analyses


def _build_excluded_metrics_section(
    excluded_by_keyword: List[str],
    excluded_by_limit: List[str],
) -> str:
    """Build HTML section showing excluded metrics by filter type.
    
    Args:
        excluded_by_keyword: List of metrics excluded by user keyword filter
        excluded_by_limit: List of metrics excluded by limit filter
        
    Returns:
        HTML string for the excluded metrics section, or empty string if none excluded
    """
    if not excluded_by_keyword and not excluded_by_limit:
        return ""
    
    # Sort both lists alphabetically for consistent display
    keyword_sorted = sorted(excluded_by_keyword, key=str.lower)
    limit_sorted = sorted(excluded_by_limit, key=str.lower)
    
    total_excluded = len(keyword_sorted) + len(limit_sorted)
    
    # Build keyword filter section
    keyword_section = ""
    if keyword_sorted:
        keyword_items = ''.join([
            f'<span class="inline-block px-2 py-1 bg-purple-100 text-purple-700 rounded text-sm font-medium">{metric}</span>'
            for metric in keyword_sorted
        ])
        keyword_section = f'''
        <div class="mb-6">
            <div class="flex items-center gap-2 mb-3">
                <svg class="w-5 h-5 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"></path>
                </svg>
                <h4 class="text-base font-semibold text-purple-800">Filtered by User Keywords ({len(keyword_sorted)})</h4>
            </div>
            <div class="flex flex-wrap gap-2">
                {keyword_items}
            </div>
        </div>
        '''
    
    # Build limit filter section
    limit_section = ""
    if limit_sorted:
        limit_items = ''.join([
            f'<span class="inline-block px-2 py-1 bg-gray-100 text-gray-700 rounded text-sm font-medium">{metric}</span>'
            for metric in limit_sorted
        ])
        limit_section = f'''
        <div class="mb-4">
            <div class="flex items-center gap-2 mb-3">
                <svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"></path>
                </svg>
                <h4 class="text-base font-semibold text-gray-700">Filtered by Missing Limits ({len(limit_sorted)})</h4>
            </div>
            <div class="flex flex-wrap gap-2">
                {limit_items}
            </div>
        </div>
        '''
    
    return f'''
    <section class="mt-10 bg-slate-50 border border-slate-200 rounded-2xl p-6">
        <div class="flex items-center gap-3 mb-5">
            <div class="p-2 bg-slate-200 rounded-lg">
                <svg class="w-6 h-6 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"></path>
                </svg>
            </div>
            <div>
                <h3 class="text-lg font-bold text-slate-800">Excluded Metrics</h3>
                <p class="text-sm text-slate-500">{total_excluded} metric(s) were excluded from this analysis</p>
            </div>
        </div>
        {keyword_section}
        {limit_section}
    </section>
    '''


def create_html_report(
    metrics_analyses: List[dict],
    portfolio_summary: str,
    file_name: str,
    use_llm: bool,
    excluded_by_keyword: Optional[List[str]] = None,
    excluded_by_limit: Optional[List[str]] = None,
) -> str:
    """Create a comprehensive HTML report with modern Tailwind CSS design.
    
    Features:
    - Light mode design with clean, professional styling
    - Sticky navigation with real-time search filtering
    - Responsive layout for all device sizes
    - Priority metrics (VaR, SVaR, STTHH) displayed first, then others sorted by name/maturity
    - Smooth scrolling and interactive UI elements
    - Excluded metrics section showing filtered metrics
    
    Args:
        metrics_analyses: List of metric analysis dictionaries
        portfolio_summary: AI-generated portfolio summary
        file_name: Name of the uploaded file
        use_llm: Whether AI insights were enabled
        excluded_by_keyword: List of metrics excluded by user keyword filter
        excluded_by_limit: List of metrics excluded by limit filter
    """
    # Default to empty lists if not provided
    excluded_by_keyword = excluded_by_keyword or []
    excluded_by_limit = excluded_by_limit or []
    
    # Sort metrics by priority (VaR, SVaR, STTHH first) then by name and maturity
    metrics_analyses_sorted = _sort_metrics_by_priority(metrics_analyses)
    metric_count = len(metrics_analyses_sorted)

    counts = kpi_counts(metrics_analyses_sorted)
    attention = [a for a in metrics_analyses_sorted if metric_status(a) != "ok"]
    attention_rows = []
    for a in attention:
        st_ = metric_status(a)
        icon = "⛔" if st_ == "breach" else "⚠️"
        n_breach = sum(b["count"] for b in a.get("breaches", []))
        detail = f"{n_breach} breaches" if st_ == "breach" else f"{len(a.get('outliers', []))} outliers"
        anchor = make_anchor_id(a["metric"])
        attention_rows.append(
            f'<tr class="border-b border-gray-100 hover:bg-gray-50">'
            f'<td class="py-2 px-3">{icon}</td>'
            f'<td class="py-2 px-3 font-medium">{a["metric"]}</td>'
            f'<td class="py-2 px-3 text-gray-600">{detail}</td>'
            f'<td class="py-2 px-3"><a href="#{anchor}" class="text-blue-600 hover:underline">jump →</a></td>'
            f'</tr>'
        )
    attention_table = (
        f'<div class="overflow-x-auto"><table class="w-full text-sm">'
        f'<thead><tr class="text-left text-gray-500"><th class="py-2 px-3"></th>'
        f'<th class="py-2 px-3">Metric</th><th class="py-2 px-3">Issue</th>'
        f'<th class="py-2 px-3"></th></tr></thead><tbody>{"".join(attention_rows)}</tbody></table></div>'
        if attention_rows else
        '<p class="text-emerald-600 font-medium">No breaches or outliers detected.</p>'
    )

    # Build navigation items (priority sorted: VaR, SVaR, STTHH first)
    toc_items = []
    for analysis in metrics_analyses_sorted:
        metric = analysis["metric"]
        anchor_id = make_anchor_id(metric)
        toc_items.append(f'''
            <a href="#{anchor_id}" 
               class="metric-nav-item group p-3 bg-white hover:bg-blue-50 border border-gray-200 hover:border-blue-400 rounded-xl transition-all duration-200 shadow-sm hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
                <div class="flex items-center gap-2">
                    <div class="w-2 h-2 rounded-full bg-blue-500 group-hover:bg-blue-600 transition-colors flex-shrink-0"></div>
                    <span class="text-sm font-medium text-gray-700 group-hover:text-blue-600 truncate transition-colors">{metric}</span>
                </div>
            </a>
        ''')
    
    # Build metric sections (priority sorted: VaR, SVaR, STTHH first)
    metric_sections = []
    for analysis in metrics_analyses_sorted:
        status = metric_status(analysis)
        border = {"breach": "border-l-4 border-l-red-500",
                  "outlier": "border-l-4 border-l-amber-400",
                  "ok": "border-l-4 border-l-emerald-400"}[status]
        metric = analysis["metric"]
        anchor_id = make_anchor_id(metric)
        stats = analysis["stats"]
        outliers = analysis["outliers"]
        outlier_dates = analysis.get("outlier_dates", [])
        breaches = analysis["breaches"]
        insights = analysis["insights"]
        fig = analysis["fig"]
        scale_context = analysis.get("scale_context")

        plot_div_id = f"plot-{make_anchor_id(metric)}"
        fig_json = fig.to_json()
        fig_html = (
            f'<div id="{plot_div_id}" class="lazy-plot" '
            f'style="min-height:420px"></div>'
            f'<script type="application/json" class="plot-spec" '
            f'data-target="{plot_div_id}">{fig_json}</script>'
        )

        # Generate limit annotation HTML if adaptive scaling was applied
        limit_annotation_html = ""
        if scale_context is not None and scale_context.needs_adaptive_scaling:
            limit_annotation_html = create_limit_annotation_html(scale_context, has_breaches=bool(breaches))

        # Outlier alert box
        outlier_html = ""
        if len(outliers) > 0:
            date_list = ", ".join(outlier_dates[:10])
            more_flag = "" if len(outlier_dates) <= 10 else "…"
            sample_values = ', '.join([f'{v:.4f}' for v in outliers[:5]])
            outlier_html = f'''
            <div class="bg-amber-50 border border-amber-200 rounded-xl p-5 mb-6">
                <div class="flex items-start gap-3">
                    <div class="flex-shrink-0">
                        <svg class="w-6 h-6 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                        </svg>
                    </div>
                    <div class="flex-1 min-w-0">
                        <h4 class="text-base font-semibold text-amber-800 mb-2">Detected Outliers (±2 SD)</h4>
                        <div class="space-y-1 text-sm text-amber-700">
                            <p><span class="font-medium">Total outliers:</span> {len(outliers)}</p>
                            <p><span class="font-medium">Sample values:</span> {sample_values}</p>
                            <p><span class="font-medium">Dates:</span> {date_list}{more_flag}</p>
                        </div>
                    </div>
                </div>
            </div>
            '''

        # Breach alert box
        breach_html = ""
        if breaches:
            breach_items = []
            for breach in breaches:
                label = "Max" if breach["type"] == "max" else "Min"
                icon_color = "text-red-500" if breach["type"] == "max" else "text-orange-500"
                date_str = ", ".join(breach["dates"][:10])
                more_flag = "" if len(breach["dates"]) <= 10 else "…"
                breach_items.append(f'''
                    <li class="flex items-start gap-2">
                        <svg class="w-5 h-5 {icon_color} flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        <span><strong>{label} limit</strong> breached {breach['count']} times on {date_str}{more_flag}</span>
                    </li>
                ''')

            breach_html = f'''
            <div class="bg-red-50 border border-red-200 rounded-xl p-5 mb-6">
                <div class="flex items-start gap-3">
                    <div class="flex-shrink-0">
                        <svg class="w-6 h-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                        </svg>
                    </div>
                    <div class="flex-1 min-w-0">
                        <h4 class="text-base font-semibold text-red-800 mb-3">Limit Breaches Detected</h4>
                        <ul class="space-y-2 text-sm text-red-700">
                            {''.join(breach_items)}
                        </ul>
                    </div>
                </div>
            </div>
            '''

        # AI insights section
        insights_html = ""
        if use_llm:
            insight_text = (insights or "No AI insight generated.").replace(chr(10), '<br><br>')
            insights_html = f'''
            <div class="mt-8 bg-gradient-to-br from-blue-50 to-cyan-50 border border-blue-200 rounded-xl p-6">
                <div class="flex items-center gap-3 mb-4">
                    <div class="p-2 bg-blue-100 rounded-lg">
                        <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path>
                        </svg>
                    </div>
                    <h3 class="text-lg font-semibold text-blue-900">AI-Generated Insights</h3>
                </div>
                <div class="prose prose-sm max-w-none text-gray-700 leading-relaxed">
                    {insight_text}
                </div>
            </div>
            '''

        metric_section = f'''
        <article id="{anchor_id}" data-status="{status}" data-metric="{metric.lower()}"
                 class="metric-card mb-10 bg-white border border-gray-200 {border} rounded-2xl shadow-lg overflow-hidden scroll-mt-32">
            <!-- Metric Header -->
            <div class="bg-gradient-to-r from-gray-50 to-white border-b border-gray-100 px-6 py-5 sm:px-8 sm:py-6">
                <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div class="flex items-center gap-3">
                        <div class="p-2 bg-blue-100 rounded-lg">
                            <svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                            </svg>
                        </div>
                        <h2 class="text-2xl sm:text-3xl font-bold text-gray-900">{metric}</h2>
                    </div>
                    <a href="#top" class="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 border border-gray-200 rounded-lg text-gray-600 hover:text-gray-800 transition-all text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-500">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 10l7-7m0 0l7 7m-7-7v18"></path>
                        </svg>
                        <span>Back to top</span>
                    </a>
                </div>
            </div>
            
            <!-- Metric Content -->
            <div class="p-6 sm:p-8">
                <!-- Stats Grid -->
                <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
                    <div class="bg-slate-700 rounded-xl p-4 text-white shadow-md">
                        <div class="text-xs font-medium text-slate-300 uppercase tracking-wide mb-1">Mean</div>
                        <div class="text-xl sm:text-2xl font-bold font-mono">{stats['mean']:.4f}</div>
                    </div>
                    <div class="bg-slate-700 rounded-xl p-4 text-white shadow-md">
                        <div class="text-xs font-medium text-slate-300 uppercase tracking-wide mb-1">Median</div>
                        <div class="text-xl sm:text-2xl font-bold font-mono">{stats['median']:.4f}</div>
                    </div>
                    <div class="bg-slate-700 rounded-xl p-4 text-white shadow-md">
                        <div class="text-xs font-medium text-slate-300 uppercase tracking-wide mb-1">Std Dev</div>
                        <div class="text-xl sm:text-2xl font-bold font-mono">{stats['std']:.4f}</div>
                    </div>
                    <div class="bg-slate-700 rounded-xl p-4 text-white shadow-md">
                        <div class="text-xs font-medium text-slate-300 uppercase tracking-wide mb-1">Min</div>
                        <div class="text-xl sm:text-2xl font-bold font-mono">{stats['min']:.4f}</div>
                    </div>
                    <div class="bg-slate-700 rounded-xl p-4 text-white shadow-md col-span-2 sm:col-span-1">
                        <div class="text-xs font-medium text-slate-300 uppercase tracking-wide mb-1">Max</div>
                        <div class="text-xl sm:text-2xl font-bold font-mono">{stats['max']:.4f}</div>
                    </div>
                </div>
                
                <!-- Alerts -->
                {outlier_html}
                {breach_html}
                {limit_annotation_html}
                
                <!-- Chart -->
                <div class="bg-gray-50 rounded-xl p-4 border border-gray-100">
                    {fig_html}
                </div>
                
                <!-- AI Insights -->
                {insights_html}
            </div>
        </article>
        '''
        metric_sections.append(metric_section)

    # Portfolio summary section
    portfolio_html = ""
    if use_llm and len(metrics_analyses) > 1 and portfolio_summary:
        portfolio_content = portfolio_summary.replace(chr(10), '<br><br>')
        portfolio_html = f'''
        <section class="mb-10 bg-gradient-to-br from-blue-50 via-cyan-50 to-white border border-blue-200 rounded-2xl shadow-lg overflow-hidden">
            <div class="bg-gradient-to-r from-blue-600 to-cyan-600 px-6 py-5 sm:px-8">
                <div class="flex items-center gap-3">
                    <div class="p-2 bg-white/20 rounded-lg">
                        <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                        </svg>
                    </div>
                    <h2 class="text-2xl font-bold text-white">Risk Portfolio Summary</h2>
                </div>
            </div>
            <div class="p-6 sm:p-8">
                <div class="prose prose-lg max-w-none text-gray-700 leading-relaxed">
                    {portfolio_content}
                </div>
            </div>
        </section>
        '''

    # Footer content
    ai_status_badge = (
        '<span class="inline-flex items-center gap-1.5 px-3 py-1 bg-emerald-100 text-emerald-700 rounded-full text-sm font-medium"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>AI Enabled</span>'
        if use_llm
        else '<span class="inline-flex items-center gap-1.5 px-3 py-1 bg-gray-100 text-gray-600 rounded-full text-sm font-medium"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>AI Disabled</span>'
    )
    disclaimer_text = "Generated by AI, use with caution." if use_llm else "Generated automatically, review before use."

    # Build excluded metrics section
    excluded_section_html = _build_excluded_metrics_section(excluded_by_keyword, excluded_by_limit)

    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Risk Metrics Analysis Report - {file_name}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    fontFamily: {{
                        sans: ['Inter', 'system-ui', 'sans-serif'],
                        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
                    }},
                }}
            }}
        }}
    </script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
    <style>
        html {{ scroll-behavior: smooth; }}
        body {{ font-family: 'Inter', system-ui, sans-serif; }}
        .font-mono {{ font-family: 'JetBrains Mono', Consolas, monospace; }}
        @keyframes pulse-dot {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}
        .animate-pulse-dot {{ animation: pulse-dot 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }}
        @media print {{
            .no-print {{ display: none !important; }}
            .print-break {{ page-break-before: always; }}
        }}
    </style>
</head>
<body class="bg-gray-50 text-gray-900 antialiased">
    <!-- Scroll Progress Bar -->
    <div id="scrollProgress" class="fixed top-0 left-0 h-1 bg-gradient-to-r from-blue-600 to-cyan-500 z-50 transition-all duration-150" style="width: 0%"></div>
    
    <div id="top" class="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
        <!-- Header -->
        <header class="text-center mb-10">
            <h1 class="text-4xl sm:text-5xl lg:text-6xl font-bold mb-6 bg-gradient-to-r from-gray-900 via-blue-800 to-blue-600 bg-clip-text text-transparent">
                Risk Metrics Dashboard
            </h1>
            <div class="flex flex-wrap items-center justify-center gap-3">
                <span class="inline-flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-full text-sm font-medium text-gray-700 shadow-sm">
                    <svg class="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                    {file_name}
                </span>
                <span class="inline-flex items-center gap-2 px-4 py-2 bg-blue-50 border border-blue-200 rounded-full text-sm font-medium text-blue-700">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                    </svg>
                    {metric_count} Metrics
                </span>
                {ai_status_badge}
            </div>
        </header>
        
        <!-- KPI strip -->
        <section class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
            <div class="bg-white border border-gray-200 rounded-xl p-4 text-center shadow-sm">
                <div class="text-3xl font-bold text-gray-900">{counts['total']}</div>
                <div class="text-xs uppercase tracking-wide text-gray-500">Metrics</div>
            </div>
            <div class="bg-red-50 border border-red-200 rounded-xl p-4 text-center shadow-sm">
                <div class="text-3xl font-bold text-red-600">{counts['breach']}</div>
                <div class="text-xs uppercase tracking-wide text-red-500">Breaching</div>
            </div>
            <div class="bg-amber-50 border border-amber-200 rounded-xl p-4 text-center shadow-sm">
                <div class="text-3xl font-bold text-amber-600">{counts['outlier']}</div>
                <div class="text-xs uppercase tracking-wide text-amber-500">Outliers</div>
            </div>
            <div class="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center shadow-sm">
                <div class="text-3xl font-bold text-emerald-600">{counts['ok']}</div>
                <div class="text-xs uppercase tracking-wide text-emerald-500">OK</div>
            </div>
        </section>
        <!-- Needs attention -->
        <section class="mb-8 bg-white border border-gray-200 rounded-2xl shadow-sm p-5">
            <h2 class="text-lg font-bold text-gray-800 mb-3">Needs attention</h2>
            {attention_table}
        </section>

        <!-- Sticky Navigation -->
        <nav id="stickyNav" class="sticky top-2 z-40 mb-10 bg-white/95 backdrop-blur-md border border-gray-200 rounded-2xl shadow-xl no-print">
            <div class="p-4 sm:p-5">
                <!-- Search and Controls -->
                <div class="flex items-center gap-3 flex-wrap">
                    <div class="flex gap-2" id="statusChips">
                        <button data-status="all" class="status-chip px-3 py-1.5 rounded-lg text-sm font-medium bg-blue-600 text-white">All</button>
                        <button data-status="breach" class="status-chip px-3 py-1.5 rounded-lg text-sm font-medium bg-red-100 text-red-700">Breaches</button>
                        <button data-status="outlier" class="status-chip px-3 py-1.5 rounded-lg text-sm font-medium bg-amber-100 text-amber-700">Outliers</button>
                        <button data-status="ok" class="status-chip px-3 py-1.5 rounded-lg text-sm font-medium bg-emerald-100 text-emerald-700">OK</button>
                    </div>
                    <div class="flex-1 relative">
                        <div class="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                            <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
                            </svg>
                        </div>
                        <input type="text" id="searchInput" placeholder="Search metrics..." 
                               class="w-full pl-12 pr-12 py-3 bg-gray-50 border border-gray-200 rounded-xl text-gray-900 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all">
                        <button id="clearSearch" class="absolute inset-y-0 right-0 pr-4 flex items-center text-gray-400 hover:text-gray-600 hidden" aria-label="Clear search">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                            </svg>
                        </button>
                    </div>
                    <span id="visibleCount" class="text-sm font-medium text-gray-600 whitespace-nowrap hidden sm:inline">{metric_count} metrics</span>
                    <button id="toggleNav" class="p-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-gray-600 transition-colors flex items-center gap-2" aria-label="Toggle navigation">
                        <svg id="toggleIcon" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                        </svg>
                        <span class="text-sm font-medium hidden sm:inline">Browse</span>
                    </button>
                </div>
                
                <!-- Navigation Grid (collapsible) -->
                <div id="navContainer" class="hidden mt-4 max-h-64 overflow-y-auto">
                    <div id="navGrid" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 pr-2">
                        {''.join(toc_items)}
                    </div>
                    
                    <!-- Empty State -->
                    <div id="emptyState" class="hidden py-8 text-center">
                        <svg class="w-12 h-12 mx-auto text-gray-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        <p class="text-gray-500 font-medium">No metrics found</p>
                        <p class="text-gray-400 text-sm mt-1">Try a different search term</p>
                    </div>
                </div>
            </div>
        </nav>
        
        <!-- Metric Sections -->
        <main>
            {''.join(metric_sections)}
        </main>
        
        <!-- Portfolio Summary -->
        {portfolio_html}
        
        <!-- Excluded Metrics Section -->
        {excluded_section_html}
        
        <!-- Footer -->
        <footer class="mt-12 pt-8 border-t border-gray-200">
            <div class="text-center">
                <p class="text-sm text-gray-500">{disclaimer_text}</p>
            </div>
        </footer>
    </div>
    
    <!-- JavaScript -->
    <script>
        (function() {{
            // Scroll Progress Bar
            const progressBar = document.getElementById('scrollProgress');
            window.addEventListener('scroll', () => {{
                const scrollTop = window.scrollY;
                const docHeight = document.documentElement.scrollHeight - window.innerHeight;
                const progress = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
                progressBar.style.width = progress + '%';
            }});
            
            // Search Functionality
            const searchInput = document.getElementById('searchInput');
            const clearSearch = document.getElementById('clearSearch');
            const metricItems = document.querySelectorAll('.metric-nav-item');
            const visibleCount = document.getElementById('visibleCount');
            const emptyState = document.getElementById('emptyState');
            const navGrid = document.getElementById('navGrid');
            const navContainer = document.getElementById('navContainer');
            const totalMetrics = {metric_count};
            
            function updateVisibility(searchTerm) {{
                let count = 0;
                searchTerm = searchTerm.toLowerCase().trim();
                
                metricItems.forEach(item => {{
                    const text = item.textContent.toLowerCase();
                    if (!searchTerm || text.includes(searchTerm)) {{
                        item.classList.remove('hidden');
                        count++;
                    }} else {{
                        item.classList.add('hidden');
                    }}
                }});
                
                visibleCount.textContent = count + ' metric' + (count !== 1 ? 's' : '');
                
                if (count === 0) {{
                    emptyState.classList.remove('hidden');
                    navGrid.classList.add('hidden');
                }} else {{
                    emptyState.classList.add('hidden');
                    navGrid.classList.remove('hidden');
                }}
                
                // Show/hide clear button
                if (searchTerm) {{
                    clearSearch.classList.remove('hidden');
                }} else {{
                    clearSearch.classList.add('hidden');
                }}
            }}
            
            searchInput.addEventListener('input', (e) => {{
                updateVisibility(e.target.value);
            }});
            
            clearSearch.addEventListener('click', () => {{
                searchInput.value = '';
                updateVisibility('');
                searchInput.focus();
            }});
            
            // Navigation Panel Toggle (collapsible)
            const toggleNav = document.getElementById('toggleNav');
            const toggleIcon = document.getElementById('toggleIcon');
            let navExpanded = false;
            
            toggleNav.addEventListener('click', () => {{
                navExpanded = !navExpanded;
                if (navExpanded) {{
                    navContainer.classList.remove('hidden');
                    updateVisibility(searchInput.value);
                    toggleIcon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7"></path>';
                }} else {{
                    navContainer.classList.add('hidden');
                    toggleIcon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>';
                }}
            }});
            
            // Smooth scrolling for anchor links
            document.querySelectorAll('a[href^="#"]').forEach(anchor => {{
                anchor.addEventListener('click', function(e) {{
                    const href = this.getAttribute('href');
                    if (href && href !== '#') {{
                        const target = document.querySelector(href);
                        if (target) {{
                            e.preventDefault();
                            target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                        }}
                    }}
                }});
            }});
            
            // Keyboard navigation for search
            searchInput.addEventListener('keydown', (e) => {{
                if (e.key === 'Escape') {{
                    searchInput.value = '';
                    updateVisibility('');
                    searchInput.blur();
                }}
            }});

            // Lazy-render Plotly charts only when scrolled into view
            const renderPlot = (specEl) => {{
                if (specEl.dataset.rendered) return;
                const target = document.getElementById(specEl.dataset.target);
                if (!target) return;
                const spec = JSON.parse(specEl.textContent);
                Plotly.newPlot(target, spec.data, spec.layout, {{responsive: true, displayModeBar: false}});
                specEl.dataset.rendered = "1";
            }};
            const plotObserver = new IntersectionObserver((entries) => {{
                entries.forEach(entry => {{
                    if (entry.isIntersecting) {{
                        renderPlot(entry.target);
                        plotObserver.unobserve(entry.target);
                    }}
                }});
            }}, {{rootMargin: "200px"}});
            document.querySelectorAll('.plot-spec').forEach(el => plotObserver.observe(el));

            // Filter metric cards by status chip + search text
            const cards = document.querySelectorAll('.metric-card');
            let activeStatus = "all";
            function applyCardFilter() {{
                const term = (searchInput.value || "").toLowerCase().trim();
                cards.forEach(card => {{
                    const matchStatus = activeStatus === "all" || card.dataset.status === activeStatus;
                    const matchText = !term || card.dataset.metric.includes(term);
                    card.style.display = (matchStatus && matchText) ? "" : "none";
                }});
            }}
            document.querySelectorAll('.status-chip').forEach(chip => {{
                chip.addEventListener('click', () => {{
                    activeStatus = chip.dataset.status;
                    document.querySelectorAll('.status-chip').forEach(c => {{
                        c.classList.toggle('ring-2', c === chip);
                        c.classList.toggle('ring-offset-1', c === chip);
                    }});
                    applyCardFilter();
                }});
            }});
            searchInput.addEventListener('input', applyCardFilter);
        }})();
    </script>
</body>
</html>'''

    return html_content


def create_export_package(
    metrics_analyses: List[dict],
    portfolio_summary: str,
    file_name: str,
    use_llm: bool,
    excluded_by_keyword: Optional[List[str]] = None,
    excluded_by_limit: Optional[List[str]] = None,
    long_dataset_csv: Optional[str] = None,
) -> BytesIO:
    """Create a ZIP archive containing the report, charts, and summary text."""
    html_content = create_html_report(
        metrics_analyses,
        portfolio_summary,
        file_name,
        use_llm,
        excluded_by_keyword=excluded_by_keyword,
        excluded_by_limit=excluded_by_limit,
    )

    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("risk_analysis_report.html", html_content)
        if long_dataset_csv:
            zip_file.writestr("powerbi_dataset.csv", long_dataset_csv)

        for analysis in metrics_analyses:
            metric = analysis["metric"]
            fig = analysis["fig"]
            img_bytes = pio.to_image(fig, format="png", width=1200, height=600, scale=2)
            zip_file.writestr(f"charts/{metric.replace('/', '_')}_chart.png", img_bytes)

        summary_text = f"""Risk Metrics Analysis Summary
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Source File: {file_name}
Metrics Analyzed: {', '.join([a['metric'] for a in metrics_analyses])}
AI Analysis Mode: {'Enabled (Google Gemini)' if use_llm else 'Disabled'}

{'='*80}

"""

        for analysis in metrics_analyses:
            metric = analysis["metric"]
            stats = analysis["stats"]
            insights = analysis["insights"]
            breaches = analysis["breaches"]

            breach_text = ""
            if breaches:
                formatted = []
                for breach in breaches:
                    label = "Max" if breach["type"] == "max" else "Min"
                    date_str = ", ".join(breach["dates"])
                    formatted.append(f"  - {label} limit breached {breach['count']} times on {date_str}")
                breach_text = "\n\nLimit Breaches:\n" + "\n".join(formatted)

            summary_text += f"""
{metric} ANALYSIS
{'='*80}

Statistics:
- Mean: {stats['mean']:.4f}
- Median: {stats['median']:.4f}
- Standard Deviation: {stats['std']:.4f}
- Min: {stats['min']:.4f}
- Max: {stats['max']:.4f}{breach_text}

"""

            if use_llm:
                summary_text += f"""

AI Insights:
{insights or 'No AI insight generated.'}

{'='*80}

"""
            else:
                summary_text += f"""

{'='*80}

"""

        if use_llm and portfolio_summary:
            summary_text += f"""
RISK PORTFOLIO SUMMARY
{'='*80}

{portfolio_summary}
"""

        zip_file.writestr("summary.txt", summary_text)

    zip_buffer.seek(0)
    return zip_buffer


def create_batch_export_package(
    batch_results: Dict[str, List[dict]],
    batch_portfolio_summaries: Dict[str, str],
    file_name: str,
    use_llm: bool,
    excluded_by_keyword: Optional[List[str]] = None,
    excluded_by_limit: Optional[List[str]] = None,
    long_dataset_csv: Optional[str] = None,
) -> BytesIO:
    """Create a ZIP archive with node-folder structure for batch mode exports.
    
    Creates a folder structure where each node has its own subdirectory containing:
    - report.html: The HTML report for that node
    - charts/: Directory with PNG images for each metric
    - summary.txt: Text summary of the analysis
    
    Args:
        batch_results: Dictionary mapping node names to their metrics_analyses lists.
        batch_portfolio_summaries: Dictionary mapping node names to portfolio summaries.
        file_name: Original source file name.
        use_llm: Whether LLM analysis was enabled.
        excluded_by_keyword: List of metrics excluded by user keyword filter.
        excluded_by_limit: List of metrics excluded by limit filter.
        
    Returns:
        BytesIO buffer containing the ZIP archive.
    """
    # Default to empty lists if not provided
    excluded_by_keyword = excluded_by_keyword or []
    excluded_by_limit = excluded_by_limit or []
    
    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        if long_dataset_csv:
            zip_file.writestr("powerbi_dataset.csv", long_dataset_csv)

        for node_name, metrics_analyses in batch_results.items():
            safe_node_name = sanitize_node_name(node_name)
            portfolio_summary = batch_portfolio_summaries.get(node_name, "")
            
            # Generate HTML report for this node
            html_content = create_html_report(
                metrics_analyses, 
                portfolio_summary, 
                f"{file_name} - {node_name}", 
                use_llm,
                excluded_by_keyword=excluded_by_keyword,
                excluded_by_limit=excluded_by_limit,
            )
            zip_file.writestr(f"{safe_node_name}/report.html", html_content)
            
            # Generate chart images
            for analysis in metrics_analyses:
                metric = analysis["metric"]
                fig = analysis["fig"]
                img_bytes = pio.to_image(fig, format="png", width=1200, height=600, scale=2)
                safe_metric = metric.replace('/', '_')
                zip_file.writestr(
                    f"{safe_node_name}/charts/{safe_metric}_chart.png", 
                    img_bytes
                )
            
            # Generate summary text
            summary_text = _create_node_summary_text(
                node_name, metrics_analyses, portfolio_summary, file_name, use_llm
            )
            zip_file.writestr(f"{safe_node_name}/summary.txt", summary_text)
    
    zip_buffer.seek(0)
    return zip_buffer


def _create_node_summary_text(
    node_name: str,
    metrics_analyses: List[dict],
    portfolio_summary: str,
    file_name: str,
    use_llm: bool,
) -> str:
    """Create the summary text file content for a single node."""
    summary_text = f"""Risk Metrics Analysis Summary - {node_name}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Source File: {file_name}
Node: {node_name}
Metrics Analyzed: {', '.join([a['metric'] for a in metrics_analyses])}
AI Analysis Mode: {'Enabled (Google Gemini)' if use_llm else 'Disabled'}

{'='*80}

"""

    for analysis in metrics_analyses:
        metric = analysis["metric"]
        stats = analysis["stats"]
        insights = analysis["insights"]
        breaches = analysis["breaches"]

        breach_text = ""
        if breaches:
            formatted = []
            for breach in breaches:
                label = "Max" if breach["type"] == "max" else "Min"
                date_str = ", ".join(breach["dates"])
                formatted.append(f"  - {label} limit breached {breach['count']} times on {date_str}")
            breach_text = "\n\nLimit Breaches:\n" + "\n".join(formatted)

        summary_text += f"""
{metric} ANALYSIS
{'='*80}

Statistics:
- Mean: {stats['mean']:.4f}
- Median: {stats['median']:.4f}
- Standard Deviation: {stats['std']:.4f}
- Min: {stats['min']:.4f}
- Max: {stats['max']:.4f}{breach_text}

"""

        if use_llm:
            summary_text += f"""

AI Insights:
{insights or 'No AI insight generated.'}

{'='*80}

"""
        else:
            summary_text += f"""

{'='*80}

"""

    if use_llm and portfolio_summary:
        summary_text += f"""
RISK PORTFOLIO SUMMARY - {node_name}
{'='*80}

{portfolio_summary}
"""

    return summary_text


__all__ = [
    "create_batch_export_package",
    "create_export_package",
    "create_html_report",
    "kpi_counts",
    "make_anchor_id",
    "metric_status",
    "sanitize_node_name",
]
