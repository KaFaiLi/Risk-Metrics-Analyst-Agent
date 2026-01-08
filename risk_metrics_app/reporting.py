from datetime import datetime
from io import BytesIO
from typing import Dict, List
import zipfile
import re

import plotly.io as pio

from .visuals import create_limit_annotation_html


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


def create_html_report(
    metrics_analyses: List[dict], portfolio_summary: str, file_name: str, use_llm: bool
) -> str:
    """Create a comprehensive HTML report with modern Tailwind CSS design.
    
    Features:
    - Light mode design with clean, professional styling
    - Sticky navigation with real-time search filtering
    - Responsive layout for all device sizes
    - Alphabetically sorted metrics for easy scanning
    - Smooth scrolling and interactive UI elements
    """
    # Sort metrics alphabetically for better navigation
    metrics_analyses_sorted = sorted(metrics_analyses, key=lambda x: x["metric"].lower())
    metric_count = len(metrics_analyses_sorted)
    
    # Build navigation items (alphabetically sorted)
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
    
    # Build metric sections (alphabetically sorted)
    metric_sections = []
    for analysis in metrics_analyses_sorted:
        metric = analysis["metric"]
        anchor_id = make_anchor_id(metric)
        stats = analysis["stats"]
        outliers = analysis["outliers"]
        outlier_dates = analysis.get("outlier_dates", [])
        breaches = analysis["breaches"]
        insights = analysis["insights"]
        fig = analysis["fig"]
        scale_context = analysis.get("scale_context")

        fig_html = fig.to_html(include_plotlyjs="cdn", div_id=f"plot-{metric.replace('/', '_')}")

        # Generate limit annotation HTML if adaptive scaling was applied
        limit_annotation_html = ""
        if scale_context is not None and scale_context.needs_adaptive_scaling:
            limit_annotation_html = create_limit_annotation_html(scale_context)

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
        <article id="{anchor_id}" class="mb-10 bg-white border border-gray-200 rounded-2xl shadow-lg overflow-hidden scroll-mt-32">
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
    ai_provider_text = "Google Gemini" if use_llm else "None"
    disclaimer_text = "Generated by AI, use with caution." if use_llm else "Generated automatically, review before use."
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Risk Metrics Analysis Report - {file_name}</title>
    <script src="https://cdn.tailwindcss.com"></script>
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
        
        <!-- Sticky Navigation -->
        <nav id="stickyNav" class="sticky top-2 z-40 mb-10 bg-white/95 backdrop-blur-md border border-gray-200 rounded-2xl shadow-xl no-print">
            <div class="p-4 sm:p-5">
                <!-- Search and Controls -->
                <div class="flex items-center gap-3">
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
                <div id="navContainer" class="hidden mt-4">
                    <div id="navGrid" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
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
        }})();
    </script>
</body>
</html>'''

    return html_content


def create_export_package(
    metrics_analyses: List[dict], portfolio_summary: str, file_name: str, use_llm: bool
) -> BytesIO:
    """Create a ZIP archive containing the report, charts, and summary text."""
    html_content = create_html_report(metrics_analyses, portfolio_summary, file_name, use_llm)

    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("risk_analysis_report.html", html_content)

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
        
    Returns:
        BytesIO buffer containing the ZIP archive.
    """
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for node_name, metrics_analyses in batch_results.items():
            safe_node_name = sanitize_node_name(node_name)
            portfolio_summary = batch_portfolio_summaries.get(node_name, "")
            
            # Generate HTML report for this node
            html_content = create_html_report(
                metrics_analyses, 
                portfolio_summary, 
                f"{file_name} - {node_name}", 
                use_llm
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
    "make_anchor_id",
    "sanitize_node_name",
]
