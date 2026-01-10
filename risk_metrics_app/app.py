import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from .config import logger
from .llm import LLMRequest, get_portfolio_summary, process_llm_requests, run_async_task
from .metrics import (
    LIMIT_MAX_SUFFIX,
    LIMIT_MIN_SUFFIX,
    VALUE_DATE_COLUMN,
    calculate_statistics,
    check_limit_breaches,
    detect_node_column,
    interpolate_for_display,
    organize_metrics,
    split_by_node,
)
from .prompts import create_llm_prompt
from .reporting import create_batch_export_package, create_export_package, create_html_report, sanitize_node_name
from .visuals import (
    calculate_scale_context,
    create_limit_annotation_html,
    create_plotly_chart,
    save_and_encode_image,
)
from .extraction import extract_data_via_proxy, parse_perimeter_input


def setup_page() -> None:
    """Configure the Streamlit page."""
    st.set_page_config(page_title="Risk Metrics Analysis with AI", page_icon="📊", layout="wide")


def initialize_session_state() -> None:
    """Ensure required session state keys exist."""
    # Core analysis state
    st.session_state.setdefault("metrics_analyses", [])
    st.session_state.setdefault("portfolio_summary", None)
    st.session_state.setdefault("analysis_completed", False)
    st.session_state.setdefault("uploaded_file_name", None)
    st.session_state.setdefault("use_llm", True)
    st.session_state.setdefault("analysis_use_llm", None)
    st.session_state.setdefault("extraction_result", None)
    st.session_state.setdefault("extraction_username", "")
    st.session_state.setdefault("extraction_perimeter_raw", "")
    st.session_state.setdefault("extraction_start_date", None)
    st.session_state.setdefault("extraction_end_date", None)
    st.session_state.setdefault("filter_metrics_without_limits", False)
    
    # Batch processing state
    st.session_state.setdefault("batch_mode", False)
    st.session_state.setdefault("batch_results", {})  # Dict[str, List[dict]] - node -> analyses
    st.session_state.setdefault("batch_node_names", [])  # List of node names for tab ordering
    st.session_state.setdefault("batch_portfolio_summaries", {})  # Dict[str, str] - node -> summary
    
    # Adaptive scaling state
    st.session_state.setdefault("scale_contexts", {})  # Dict[str, ScaleContext] - metric -> context
    st.session_state.setdefault("adaptive_scale_toggles", {})  # Dict[str, bool] - metric -> enabled
    st.session_state.setdefault("use_adaptive_scaling", True)  # Global adaptive scaling toggle


def metric_has_meaningful_limits(df: pd.DataFrame, metric: str) -> bool:
    """Return True if at least one limit column contains non-zero, non-null values."""

    def _series_has_limits(column_name: str) -> bool:
        if column_name not in df.columns:
            return False
        numeric = pd.to_numeric(df[column_name], errors="coerce").dropna()
        if numeric.empty:
            return False
        return not (numeric == 0).all()

    max_col = f"{metric}{LIMIT_MAX_SUFFIX}"
    min_col = f"{metric}{LIMIT_MIN_SUFFIX}"
    return _series_has_limits(max_col) or _series_has_limits(min_col)


def reset_analysis_state() -> None:
    """Clear stored analysis results from session state."""
    # Core state
    st.session_state.metrics_analyses = []
    st.session_state.portfolio_summary = None
    st.session_state.analysis_completed = False
    st.session_state.uploaded_file_name = None
    st.session_state.analysis_use_llm = None
    
    # Batch mode state
    st.session_state.batch_mode = False
    st.session_state.batch_results = {}
    st.session_state.batch_node_names = []
    st.session_state.batch_portfolio_summaries = {}
    
    # Adaptive scaling state
    st.session_state.scale_contexts = {}
    st.session_state.adaptive_scale_toggles = {}


def render_sidebar() -> tuple[Optional[str], Optional[Any], bool, bool, bool, bool]:
    """Render sidebar controls and return core inputs."""
    with st.sidebar:
        st.header("⚙️ Configuration")

        use_llm = st.checkbox(
            "Enable AI-generated insights",
            value=st.session_state.get("use_llm", True),
            help="Toggle Google Gemini commentary. Disable to generate charts only.",
        )
        st.session_state.use_llm = use_llm

        api_key: Optional[str] = None
        if use_llm:
            api_key = st.text_input(
                "Google API Key",
                type="password",
                help="Enter your Google API key for Gemini AI analysis",
            )

            if api_key:
                os.environ["GOOGLE_API_KEY"] = api_key
        else:
            st.info("AI insights disabled. Only statistics and charts will be generated.")

        st.divider()

        filter_metrics_without_limits = st.checkbox(
            "Hide metrics without limits",
            value=st.session_state.get("filter_metrics_without_limits", False),
            help="Exclude risk metrics where both max and min limit columns are empty or zero.",
        )
        st.session_state.filter_metrics_without_limits = filter_metrics_without_limits

        use_adaptive_scaling = st.checkbox(
            "Enable adaptive graph scaling",
            value=st.session_state.get("use_adaptive_scaling", True),
            help="Zoom charts to data range when limit values are much larger than data. Limit values will be shown in annotations.",
        )
        st.session_state.use_adaptive_scaling = use_adaptive_scaling

        st.divider()

        st.subheader("📁 Upload Data")
        uploaded_file = st.file_uploader(
            "Upload CSV file",
            type=["csv"],
            help="Upload a CSV file containing ValueDate, risk metrics, and limit columns",
        )

        st.divider()
        analyze_button = st.button("🚀 Analyze Risk Metrics", type="primary", use_container_width=True)

        if st.session_state.analysis_completed:
            if st.button("🔄 Clear Results & Start New Analysis", use_container_width=True):
                reset_analysis_state()
                st.rerun()

    return api_key, uploaded_file, analyze_button, use_llm, filter_metrics_without_limits, use_adaptive_scaling


def display_welcome_panel() -> None:
    """Show guidance when no analysis has been executed yet."""
    st.info("👈 Configure your analysis settings in the sidebar and upload a CSV file to begin!")

    st.markdown(
        """
    ### How to use:
    1. **Enter your Google API Key** in the sidebar if you want AI commentary (optional)
    2. **Upload a CSV file** containing risk metrics data
    3. **Click 'Analyze Risk Metrics'** to generate charts and optional AI insights

    ### CSV File Format:
    Your CSV file should include:
    - **ValueDate**: Date column for time series data
    - **Risk Metrics**: Columns with metric values (e.g., VaR, SVaR, FTQ, IRsensi1M, etc.)
    - **Limit Columns** (optional): Max/min limits with suffix `_limMaxValue` and `_limMinValue`

    ### Metric Ordering:
    The application automatically organizes metrics in this order:
    1. **Priority Metrics**: VaR, SVaR, FTQ (displayed first)
    2. **Other Metrics**: Sorted alphabetically by name, then by maturity (1W, 1M, 3M, 1Y, 2Y, 5Y, 10Y, etc.)

    ### Features:
    - 📈 Interactive charts with statistical overlays and limit bands
    - 📊 Mean, median, and ±2 standard deviation analysis
    - 🔍 Automatic outlier detection
    - ⚠️ Limit breach identification
    - 🤖 Optional AI-powered risk analysis using Google Gemini
    - 📉 Support for multiple risk metrics simultaneously
    - 📥 Export to HTML and ZIP package

    ### Example Metrics:
    - **Market Risk**: VaR, SVaR, FTQ
    - **Interest Rate Sensitivity**: IRsensi, IRsensi1M, IRsensi1Y, IRSensi2Y, IRSensi5Y, IRSensi10Y
    - **Basis Risk**: BasisSensiByCurrencyByPillar[EUR][1W], BasisSensiByCurrencyByPillar[EUR][1M], etc.
    """
    )

    with st.expander("📋 View Sample CSV Format"):
        st.markdown(
            """
        ```
        ValueDate,VaR,SVaR,FTQ,IRsensi1M,IRsensi1Y,VaR_limMaxValue,VaR_limMinValue,SVaR_limMaxValue,SVaR_limMinValue
        2024-01-01,0.0869,0.9958,0.9900,0.6206,0.0950,0.7348,0.4746,0.2995,0.6294
        2024-01-02,0.4077,0.8874,0.0147,0.8172,0.8740,0.5992,0.7998,0.2352,0.2532
        2024-01-03,0.4325,0.5217,0.4007,0.0302,0.6670,0.8378,0.0305,0.0768,0.5859
        ```

        **Note:**
        - Limit columns are optional
        - You can have any number of risk metrics
        - Dates should be in YYYY-MM-DD format
        """
        )


def render_export_options() -> None:
    """Display export download buttons when analysis results are available."""
    st.divider()
    st.header("📥 Export Results")

    use_llm = st.session_state.get("analysis_use_llm", st.session_state.get("use_llm", True))
    batch_mode = st.session_state.get("batch_mode", False)

    if batch_mode:
        _render_batch_export_options(use_llm)
    else:
        _render_single_export_options(use_llm)


def _render_single_export_options(use_llm: bool) -> None:
    """Render export options for single-mode analysis."""
    col1, col2 = st.columns(2)

    with col1:
        html_report = create_html_report(
            st.session_state.metrics_analyses,
            st.session_state.portfolio_summary,
            st.session_state.uploaded_file_name,
            use_llm,
        )
        st.download_button(
            label="📄 Download HTML Report",
            data=html_report,
            file_name=f"risk_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            mime="text/html",
            use_container_width=True,
            key="download_html",
        )

    with col2:
        zip_buffer = create_export_package(
            st.session_state.metrics_analyses,
            st.session_state.portfolio_summary,
            st.session_state.uploaded_file_name,
            use_llm,
        )
        st.download_button(
            label="📦 Download Complete Package (ZIP)",
            data=zip_buffer,
            file_name=f"risk_analysis_package_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip",
            use_container_width=True,
            key="download_zip",
        )

    st.info(
        """
    **Export Options:**
    - **HTML Report**: Single file with interactive charts and (when enabled) AI commentary
    - **Complete Package**: ZIP file containing HTML report, chart images (PNG), and text summary

    💡 **Tip**: Your results are saved in this session. You can download multiple times or start a new analysis using the button in the sidebar.
    """,
        icon="ℹ️",
    )


def _render_batch_export_options(use_llm: bool) -> None:
    """Render export options for batch-mode analysis with node-folder structure."""
    batch_results = st.session_state.get("batch_results", {})
    batch_portfolio_summaries = st.session_state.get("batch_portfolio_summaries", {})
    
    st.markdown("**Batch Mode Export**: Downloads will be organized by node in separate folders.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Individual node export selector
        node_names = list(batch_results.keys())
        selected_node = st.selectbox(
            "Select node for individual export",
            options=node_names,
            key="export_node_selector",
        )
        
        if selected_node:
            node_analyses = batch_results.get(selected_node, [])
            node_summary = batch_portfolio_summaries.get(selected_node, "")
            
            html_report = create_html_report(
                node_analyses,
                node_summary,
                f"{st.session_state.uploaded_file_name} - {selected_node}",
                use_llm,
            )
            st.download_button(
                label=f"📄 Download {selected_node} HTML Report",
                data=html_report,
                file_name=f"risk_analysis_{sanitize_node_name(selected_node)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                mime="text/html",
                use_container_width=True,
                key="download_node_html",
            )

    with col2:
        # Full batch export with node-folder structure
        zip_buffer = create_batch_export_package(
            batch_results,
            batch_portfolio_summaries,
            st.session_state.uploaded_file_name,
            use_llm,
        )
        st.download_button(
            label="📦 Download All Nodes (ZIP)",
            data=zip_buffer,
            file_name=f"risk_analysis_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip",
            use_container_width=True,
            key="download_batch_zip",
        )

    st.info(
        """
    **Batch Export Options:**
    - **Individual Node HTML**: Export a single node's analysis as HTML
    - **All Nodes ZIP**: Download all nodes in a ZIP with folder structure:
      - `NodeA/report.html`, `NodeA/charts/`, `NodeA/summary.txt`
      - `NodeB/report.html`, `NodeB/charts/`, `NodeB/summary.txt`

    💡 **Tip**: Each node folder contains complete analysis with charts and (when enabled) AI commentary.
    """,
        icon="ℹ️",
    )


def render_extraction_tab() -> None:
    """Render the API extraction workflow inside its own tab."""
    st.header("🛠️ API Data Extraction")
    st.markdown(
        """
        Use this tool to fetch fresh risk metrics from the internal API proxy. Supply your credentials and a
        comma-separated list of perimeters to generate a CSV file saved locally for later analysis.
        
        **Date Range:** Optionally specify start and end dates to control the date range of extracted data.
        If dates are not provided, the system will use default behavior (current date minus days based on perimeter count).
        """
    )

    with st.form("api_extraction_form", clear_on_submit=False):
        username = st.text_input(
            "API Username",
            value=st.session_state.get("extraction_username", ""),
            help="Account name used for the internal data service.",
        )
        password = st.text_input(
            "API Password",
            type="password",
            help="Credentials are used only for this request and are not stored.",
        )
        perimeter_raw = st.text_input(
            "Perimeter(s)",
            value=st.session_state.get("extraction_perimeter_raw", ""),
            help="Provide one or more perimeters separated by commas, e.g. FrontOffice,London,Equities.",
        )
        
        # Date range inputs
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Start Date",
                value=st.session_state.get("extraction_start_date"),
                help="Start date for the data extraction (optional - leave empty to use default behavior).",
            )
        with col2:
            end_date = st.date_input(
                "End Date",
                value=st.session_state.get("extraction_end_date"),
                help="End date for the data extraction (optional - leave empty to use default behavior).",
            )
        
        submitted = st.form_submit_button("📥 Fetch Data", use_container_width=True)

    if submitted:
        st.session_state.extraction_username = username
        st.session_state.extraction_perimeter_raw = perimeter_raw
        st.session_state.extraction_start_date = start_date
        st.session_state.extraction_end_date = end_date
        perimeters = parse_perimeter_input(perimeter_raw)
        
        # Convert date objects to datetime if provided
        start_datetime = datetime.combine(start_date, datetime.min.time()) if start_date else None
        end_datetime = datetime.combine(end_date, datetime.min.time()) if end_date else None

        try:
            with st.spinner("Requesting API and saving CSV..."):
                _, payload = extract_data_via_proxy(
                    username, password, perimeters, start_date=start_datetime, end_date=end_datetime
                )
            st.session_state.extraction_result = payload
            st.success("✅ Data extracted successfully.")
        except ValueError as error:
            st.error(f"⚠️ {error}")
        except Exception as error:  # noqa: BLE001 - surface detailed error for debugging
            st.error("❌ Unexpected error during API extraction.")
            st.exception(error)

    result = st.session_state.get("extraction_result")
    if result:
        st.subheader("Latest Extraction Summary")
        st.markdown("**Download path**")
        st.code(result["download_path"], language="text")

        st.json(
            {
                "username": result["username"],
                "perimeters": result["perimeters"],
                "row_count": result["row_count"],
                "password_checksum": result["password_checksum"],
                "generated_at": result["generated_at"],
                "start_date": result.get("start_date"),
                "end_date": result.get("end_date"),
            }
        )

        try:
            preview_df = pd.read_csv(result["download_path"]).head()
            st.markdown("**Preview of downloaded data (first 5 rows)**")
            st.dataframe(preview_df, use_container_width=True)
        except FileNotFoundError:
            st.warning("The saved CSV could not be found at the reported path. It may have been moved or deleted.")


def handle_analysis(
    api_key: Optional[str],
    uploaded_file,
    use_llm: bool,
    filter_metrics_without_limits: bool,
) -> None:
    """Execute the risk metric analysis workflow."""
    if use_llm and not api_key:
        st.error("⚠️ Please enter your Google API Key in the sidebar to enable AI analysis.")
        return
    if uploaded_file is None:
        st.error("⚠️ Please upload a CSV file.")
        return

    reset_analysis_state()
    st.session_state.uploaded_file_name = uploaded_file.name
    st.session_state.analysis_use_llm = use_llm

    try:
        df = pd.read_csv(uploaded_file)
        df.columns = [col.lower() for col in df.columns]
        logger.info("Loaded data frame from %s with shape %s", uploaded_file.name, df.shape)

        if VALUE_DATE_COLUMN not in df.columns:
            st.error("⚠️ The uploaded file is missing the required 'ValueDate' column.")
            return

        df[VALUE_DATE_COLUMN] = pd.to_datetime(df[VALUE_DATE_COLUMN])

        # Check for node column to determine batch mode
        node_column = detect_node_column(df)
        if node_column:
            logger.info("Detected node column: %s - entering batch mode", node_column)
            st.session_state.batch_mode = True
            node_dfs = split_by_node(df, node_column)
            st.session_state.batch_node_names = list(node_dfs.keys())
            st.info(f"📊 Batch mode: Detected {len(node_dfs)} nodes ({', '.join(node_dfs.keys())})")
            
            _handle_batch_analysis(
                node_dfs, use_llm, filter_metrics_without_limits
            )
        else:
            logger.info("No node column detected - using single mode")
            st.session_state.batch_mode = False
            _handle_single_analysis(
                df, use_llm, filter_metrics_without_limits
            )

    except Exception as error:  # noqa: BLE001 - surface detailed error to user
        st.error(f"❌ Error processing file: {str(error)}")
        st.exception(error)
        logger.exception("Analysis failed due to unexpected error")


def _handle_batch_analysis(
    node_dfs: Dict[str, pd.DataFrame],
    use_llm: bool,
    filter_metrics_without_limits: bool,
) -> None:
    """Process analysis for multiple nodes in batch mode with tabs."""
    batch_results: Dict[str, List[dict]] = {}
    batch_portfolio_summaries: Dict[str, str] = {}
    
    # Create tabs for each node
    node_names = list(node_dfs.keys())
    tabs = st.tabs([f"📊 {name}" for name in node_names])
    
    for tab, node_name in zip(tabs, node_names):
        with tab:
            st.header(f"Analysis for Node: {node_name}")
            node_df = node_dfs[node_name]
            
            # Process this node's analysis
            node_analyses, node_summary = _process_node_analysis(
                node_df, node_name, use_llm, filter_metrics_without_limits
            )
            
            batch_results[node_name] = node_analyses
            batch_portfolio_summaries[node_name] = node_summary
    
    # Store results in session state
    st.session_state.batch_results = batch_results
    st.session_state.batch_portfolio_summaries = batch_portfolio_summaries
    st.session_state.analysis_completed = True
    
    if not use_llm:
        st.info("AI insights were disabled for this analysis. Charts and exports include statistics and visualizations only.")
    st.success("✅ Batch analysis complete!")
    logger.info("Batch analysis completed for %d nodes", len(node_dfs))


def _process_node_analysis(
    df: pd.DataFrame,
    node_name: str,
    use_llm: bool,
    filter_metrics_without_limits: bool,
) -> tuple[List[dict], str]:
    """Process analysis for a single node and return results."""
    ordered_metrics = organize_metrics(df)
    initial_metric_count = len(ordered_metrics)
    logger.info("Node %s: Organized %s metric(s)", node_name, initial_metric_count)

    if filter_metrics_without_limits:
        filtered_metrics = [metric for metric in ordered_metrics if metric_has_meaningful_limits(df, metric)]
        filtered_out = initial_metric_count - len(filtered_metrics)
        if filtered_out > 0:
            st.info(f"Filtered out {filtered_out} metric(s) without limit values.")
            logger.info("Node %s: Filtered out %s metric(s) without limits", node_name, filtered_out)
        ordered_metrics = filtered_metrics

    if not ordered_metrics:
        st.warning("No risk metrics available after applying the limit filter.")
        logger.warning("Node %s: No metrics available after applying limit filter", node_name)
        return [], ""

    st.success(f"✅ Loaded {len(df)} rows with {len(ordered_metrics)} risk metrics")

    metrics_analyses: List[dict] = []
    llm_requests: list[LLMRequest] = []

    for idx, metric in enumerate(ordered_metrics):
        logger.info("Node %s: Processing metric %s (%s/%s)", node_name, metric, idx + 1, len(ordered_metrics))
        st.subheader(f"📊 {metric}")

        max_limit_col = f"{metric}{LIMIT_MAX_SUFFIX}"
        min_limit_col = f"{metric}{LIMIT_MIN_SUFFIX}"
        max_limit = df[max_limit_col] if max_limit_col in df.columns else None
        min_limit = df[min_limit_col] if min_limit_col in df.columns else None

        # Forward-fill limits to handle missing days (assumes limit unchanged if not specified)
        if max_limit is not None:
            max_limit = max_limit.ffill()
        if min_limit is not None:
            min_limit = min_limit.ffill()

        metric_series = df[metric]
        stats, outliers = calculate_statistics(metric_series)
        breaches = check_limit_breaches(df, metric, max_limit, min_limit)

        # Calculate scale context for adaptive scaling
        scale_context = calculate_scale_context(
            metric_series, df[VALUE_DATE_COLUMN], max_limit, min_limit
        )
        
        # Use global adaptive scaling setting from sidebar
        use_adaptive = st.session_state.get("use_adaptive_scaling", True) and scale_context.needs_adaptive_scaling

        # Apply interpolation for display if there are gaps
        display_series = None
        if metric_series.isna().any():
            display_series = interpolate_for_display(
                metric_series, df[VALUE_DATE_COLUMN]
            )

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Mean", f"{stats['mean']:.4f}")
        with col2:
            st.metric("Median", f"{stats['median']:.4f}")
        with col3:
            st.metric("Std Dev", f"{stats['std']:.4f}")
        with col4:
            st.metric("Min", f"{stats['min']:.4f}")
        with col5:
            st.metric("Max", f"{stats['max']:.4f}")

        outlier_dates = []
        if len(outliers) > 0:
            outlier_dates = df.loc[outliers.index, VALUE_DATE_COLUMN].dt.strftime("%Y-%m-%d").tolist()
            st.info(
                "🔍 Detected {} outlier(s) (±2 SD from mean) on {}".format(
                    len(outliers), ", ".join(outlier_dates)
                )
            )
        if breaches:
            breach_messages = []
            for breach in breaches:
                label = "Max" if breach["type"] == "max" else "Min"
                dates = ", ".join(breach["dates"])
                breach_messages.append(f"{label} limit breached {breach['count']} times on {dates}")
            st.warning(f"⚠️ {'; '.join(breach_messages)}")

        with st.spinner(f"Creating chart for {metric}..."):
            fig = create_plotly_chart(
                df, metric, stats, outliers, max_limit, min_limit,
                scale_context=scale_context if use_adaptive else None,
                display_series=display_series,
            )
            st.plotly_chart(fig, use_container_width=True, key=f"chart_{node_name}_{metric}")

        # Display limit annotation banner if adaptive scaling was applied
        if use_adaptive and scale_context and scale_context.needs_adaptive_scaling and scale_context.limit_periods:
            annotation_html = create_limit_annotation_html(scale_context, has_breaches=bool(breaches))
            st.markdown(annotation_html, unsafe_allow_html=True)

        has_limits = (max_limit is not None) or (min_limit is not None)
        insights_placeholder = None
        insights_value: Optional[str] = None
        should_request_llm = False

        if use_llm:
            insights_placeholder = st.empty()

            valid_count = metric_series.count()
            zero_ratio = (metric_series == 0).sum() / valid_count if valid_count else 0.0
            if not valid_count or zero_ratio >= 0.95:
                logger.info(
                    "Skipping LLM analysis for %s due to low exposure (zero ratio %.2f)",
                    metric,
                    zero_ratio,
                )
                insight_text = "Low exposure, no insight"
                with insights_placeholder.container(border=True):
                    st.write(insight_text)
                insights_value = insight_text
            else:
                insights_placeholder.info("🤖 Generating AI insights...")
                should_request_llm = True
        else:
            insights_value = "AI analysis disabled for this run."

        metrics_analyses.append(
            {
                "metric": metric,
                "stats": stats,
                "outliers": outliers,
                "outlier_dates": outlier_dates,
                "breaches": breaches,
                "insights": insights_value,
                "fig": fig,
                "scale_context": scale_context if use_adaptive else None,
            }
        )

        analysis_index = len(metrics_analyses) - 1

        if use_llm and should_request_llm and insights_placeholder is not None:
            img_base64 = save_and_encode_image(fig, f"{node_name}_{metric}")
            prompt_text = create_llm_prompt(metric, stats, outliers, breaches, has_limits)
            llm_requests.append(
                {
                    "metric": metric,
                    "prompt_text": prompt_text,
                    "img_base64": img_base64,
                    "placeholder": insights_placeholder,
                    "analysis_index": analysis_index,
                }
            )

        if idx < len(ordered_metrics) - 1:
            st.divider()

    # Process LLM requests for this node
    if use_llm and llm_requests:
        with st.spinner("Generating AI insights..."):
            llm_results = run_async_task(process_llm_requests(llm_requests))
            logger.info("Node %s: Received %s AI insight response(s)", node_name, len(llm_results))

        for request, insight in llm_results:
            placeholder = request["placeholder"]
            if insight.startswith("Error generating"):
                logger.error("Node %s: AI insight generation failed for %s", node_name, request["metric"])
                placeholder.error(insight)
            else:
                logger.info("Node %s: AI insight generation succeeded for %s", node_name, request["metric"])
                with placeholder.container(border=True):
                    st.write(insight)

            metrics_analyses[request["analysis_index"]]["insights"] = insight

    # Generate portfolio summary for this node
    portfolio_summary = ""
    if use_llm and len(metrics_analyses) > 1:
        st.divider()
        st.subheader("📋 Risk Portfolio Summary")
        st.markdown(f"*Comprehensive risk analysis for node {node_name}*")

        with st.spinner("Generating portfolio-level risk insights..."):
            portfolio_summary = get_portfolio_summary(metrics_analyses)
            if portfolio_summary.startswith("Error generating"):
                logger.error("Node %s: Portfolio summary generation failed", node_name)
            else:
                logger.info("Node %s: Portfolio summary generation succeeded", node_name)

        with st.container(border=True):
            st.write(portfolio_summary)

    return metrics_analyses, portfolio_summary


def _handle_single_analysis(
    df: pd.DataFrame,
    use_llm: bool,
    filter_metrics_without_limits: bool,
) -> None:
    """Execute the single-mode risk metric analysis workflow (legacy behavior)."""
    ordered_metrics = organize_metrics(df)
    initial_metric_count = len(ordered_metrics)
    logger.info("Organized %s metric(s)", initial_metric_count)

    if filter_metrics_without_limits:
        filtered_metrics = [metric for metric in ordered_metrics if metric_has_meaningful_limits(df, metric)]
        filtered_out = initial_metric_count - len(filtered_metrics)
        if filtered_out > 0:
            st.info(f"Filtered out {filtered_out} metric(s) without limit values.")
            logger.info("Filtered out %s metric(s) without limits", filtered_out)
        ordered_metrics = filtered_metrics

    if not ordered_metrics:
        st.warning("No risk metrics available after applying the limit filter.")
        logger.warning("No metrics available after applying limit filter")
        return

    st.success(f"✅ Loaded {len(df)} rows with {len(ordered_metrics)} risk metrics")

    metrics_analyses = []
    llm_requests: list[LLMRequest] = []

    for idx, metric in enumerate(ordered_metrics):
        logger.info("Processing metric %s (%s/%s)", metric, idx + 1, len(ordered_metrics))
        st.header(f"📊 {metric} Analysis")

        max_limit_col = f"{metric}{LIMIT_MAX_SUFFIX}"
        min_limit_col = f"{metric}{LIMIT_MIN_SUFFIX}"
        max_limit = df[max_limit_col] if max_limit_col in df.columns else None
        min_limit = df[min_limit_col] if min_limit_col in df.columns else None

        # Forward-fill limits to handle missing days (assumes limit unchanged if not specified)
        if max_limit is not None:
            max_limit = max_limit.ffill()
        if min_limit is not None:
            min_limit = min_limit.ffill()

        metric_series = df[metric]
        stats, outliers = calculate_statistics(metric_series)
        breaches = check_limit_breaches(df, metric, max_limit, min_limit)

        # Calculate scale context for adaptive scaling
        scale_context = calculate_scale_context(
            metric_series, df[VALUE_DATE_COLUMN], max_limit, min_limit
        )
        
        # Use global adaptive scaling setting from sidebar
        use_adaptive = st.session_state.get("use_adaptive_scaling", True) and scale_context.needs_adaptive_scaling

        # Apply interpolation for display if there are gaps
        display_series = None
        if metric_series.isna().any():
            display_series = interpolate_for_display(
                metric_series, df[VALUE_DATE_COLUMN]
            )

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Mean", f"{stats['mean']:.4f}")
        with col2:
            st.metric("Median", f"{stats['median']:.4f}")
        with col3:
            st.metric("Std Dev", f"{stats['std']:.4f}")
        with col4:
            st.metric("Min", f"{stats['min']:.4f}")
        with col5:
            st.metric("Max", f"{stats['max']:.4f}")

        outlier_dates = []
        if len(outliers) > 0:
            outlier_dates = df.loc[outliers.index, VALUE_DATE_COLUMN].dt.strftime("%Y-%m-%d").tolist()
            st.info(
                "🔍 Detected {} outlier(s) (±2 SD from mean) on {}".format(
                    len(outliers), ", ".join(outlier_dates)
                )
            )
        if breaches:
            breach_messages = []
            for breach in breaches:
                label = "Max" if breach["type"] == "max" else "Min"
                dates = ", ".join(breach["dates"])
                breach_messages.append(f"{label} limit breached {breach['count']} times on {dates}")
            st.warning(f"⚠️ {'; '.join(breach_messages)}")

        with st.spinner(f"Creating chart for {metric}..."):
            fig = create_plotly_chart(
                df, metric, stats, outliers, max_limit, min_limit,
                scale_context=scale_context if use_adaptive else None,
                display_series=display_series,
            )
            st.plotly_chart(fig, use_container_width=True, key=f"chart_single_{metric}")

        # Display limit annotation banner if adaptive scaling was applied
        if use_adaptive and scale_context and scale_context.needs_adaptive_scaling and scale_context.limit_periods:
            annotation_html = create_limit_annotation_html(scale_context, has_breaches=bool(breaches))
            st.markdown(annotation_html, unsafe_allow_html=True)

        has_limits = (max_limit is not None) or (min_limit is not None)
        insights_placeholder = None
        insights_value: Optional[str] = None
        should_request_llm = False

        if use_llm:
            st.subheader("🤖 AI-Generated Insights")
            insights_placeholder = st.empty()

            valid_count = metric_series.count()
            zero_ratio = (metric_series == 0).sum() / valid_count if valid_count else 0.0
            if not valid_count or zero_ratio >= 0.95:
                logger.info(
                    "Skipping LLM analysis for %s due to low exposure (zero ratio %.2f)",
                    metric,
                    zero_ratio,
                )
                insight_text = "Low exposure, no insight"
                with insights_placeholder.container(border=True):
                    st.write(insight_text)
                insights_value = insight_text
            else:
                insights_placeholder.info("🤖 Generating AI insights...")
                should_request_llm = True
        else:
            insights_value = "AI analysis disabled for this run."

        metrics_analyses.append(
            {
                "metric": metric,
                "stats": stats,
                "outliers": outliers,
                "outlier_dates": outlier_dates,
                "breaches": breaches,
                "insights": insights_value,
                "fig": fig,
                "scale_context": scale_context if use_adaptive else None,
            }
        )

        analysis_index = len(metrics_analyses) - 1

        if use_llm and should_request_llm and insights_placeholder is not None:
            img_base64 = save_and_encode_image(fig, metric)
            prompt_text = create_llm_prompt(metric, stats, outliers, breaches, has_limits)
            llm_requests.append(
                {
                    "metric": metric,
                    "prompt_text": prompt_text,
                    "img_base64": img_base64,
                    "placeholder": insights_placeholder,
                    "analysis_index": analysis_index,
                }
            )

        if idx < len(ordered_metrics) - 1:
            st.divider()

    if use_llm and llm_requests:
        with st.spinner("Generating AI insights..."):
            llm_results = run_async_task(process_llm_requests(llm_requests))
            logger.info("Received %s AI insight response(s)", len(llm_results))

        for request, insight in llm_results:
            placeholder = request["placeholder"]
            if insight.startswith("Error generating"):
                logger.error("AI insight generation failed for %s", request["metric"])
                placeholder.error(insight)
            else:
                logger.info("AI insight generation succeeded for %s", request["metric"])
                with placeholder.container(border=True):
                    st.write(insight)

            metrics_analyses[request["analysis_index"]]["insights"] = insight

    st.session_state.metrics_analyses = metrics_analyses
    st.session_state.portfolio_summary = None

    if use_llm and len(metrics_analyses) > 1:
        st.divider()
        st.header("📋 Risk Portfolio Summary")
        st.markdown("*Comprehensive risk analysis across all metrics*")

        with st.spinner("Generating portfolio-level risk insights..."):
            portfolio_summary = get_portfolio_summary(metrics_analyses)
            if portfolio_summary.startswith("Error generating"):
                logger.error("Portfolio summary generation failed")
            else:
                logger.info("Portfolio summary generation succeeded")

        with st.container(border=True):
            st.subheader("🎯 Strategic Risk Assessment")
            st.write(portfolio_summary)

        st.session_state.portfolio_summary = portfolio_summary

    st.session_state.analysis_completed = True
    if not use_llm:
        st.info("AI insights were disabled for this analysis. Charts and exports include statistics and visualizations only.")
    st.success("✅ Analysis complete!")
    logger.info("Analysis completed successfully")


def run_app() -> None:
    """Main entry point for the Streamlit application."""
    setup_page()
    initialize_session_state()

    api_key, uploaded_file, analyze_button, use_llm, filter_metrics_without_limits, use_adaptive_scaling = render_sidebar()

    analysis_tab, extraction_tab = st.tabs(["Risk Metrics Analysis", "API Extraction"])

    with analysis_tab:
        if analyze_button:
            handle_analysis(api_key, uploaded_file, use_llm, filter_metrics_without_limits)
        elif not st.session_state.analysis_completed:
            display_welcome_panel()

        # Show export options if analysis is complete
        if st.session_state.analysis_completed:
            batch_mode = st.session_state.get("batch_mode", False)
            if batch_mode:
                # Check if batch results exist
                if st.session_state.get("batch_results"):
                    render_export_options()
            else:
                # Check if single-mode results exist
                if st.session_state.get("metrics_analyses"):
                    render_export_options()

    with extraction_tab:
        render_extraction_tab()
