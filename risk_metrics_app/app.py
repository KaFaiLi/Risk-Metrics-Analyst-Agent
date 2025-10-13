import os
from datetime import datetime
from typing import Any, Optional

import pandas as pd
import streamlit as st

from .config import logger
from .llm import LLMRequest, get_portfolio_summary, process_llm_requests, run_async_task
from .metrics import calculate_statistics, check_limit_breaches, organize_metrics
from .prompts import create_llm_prompt
from .reporting import create_export_package, create_html_report
from .visuals import create_plotly_chart, save_and_encode_image
from .extraction import extract_data_via_proxy, parse_perimeter_input


def setup_page() -> None:
    """Configure the Streamlit page."""
    st.set_page_config(page_title="Risk Metrics Analysis with AI", page_icon="📊", layout="wide")


def initialize_session_state() -> None:
    """Ensure required session state keys exist."""
    st.session_state.setdefault("metrics_analyses", [])
    st.session_state.setdefault("portfolio_summary", None)
    st.session_state.setdefault("analysis_completed", False)
    st.session_state.setdefault("uploaded_file_name", None)
    st.session_state.setdefault("extraction_result", None)
    st.session_state.setdefault("extraction_username", "")
    st.session_state.setdefault("extraction_perimeter_raw", "")


def reset_analysis_state() -> None:
    """Clear stored analysis results from session state."""
    st.session_state.metrics_analyses = []
    st.session_state.portfolio_summary = None
    st.session_state.analysis_completed = False
    st.session_state.uploaded_file_name = None


def render_sidebar() -> tuple[Optional[str], Optional[Any], bool]:
    """Render sidebar controls and return core inputs."""
    with st.sidebar:
        st.header("⚙️ Configuration")

        api_key = st.text_input(
            "Google API Key",
            type="password",
            help="Enter your Google API key for Gemini AI analysis",
        )

        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key

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

    return api_key, uploaded_file, analyze_button


def display_welcome_panel() -> None:
    """Show guidance when no analysis has been executed yet."""
    st.info("👈 Configure your analysis settings in the sidebar and upload a CSV file to begin!")

    st.markdown(
        """
    ### How to use:
    1. **Enter your Google API Key** in the sidebar (required for AI analysis)
    2. **Upload a CSV file** containing risk metrics data
    3. **Click 'Analyze Risk Metrics'** to generate charts and AI insights

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
    - 🤖 AI-powered risk analysis using Google Gemini
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

    col1, col2 = st.columns(2)

    with col1:
        html_report = create_html_report(
            st.session_state.metrics_analyses,
            st.session_state.portfolio_summary,
            st.session_state.uploaded_file_name,
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
    - **HTML Report**: Single file with interactive charts and all insights
    - **Complete Package**: ZIP file containing HTML report, chart images (PNG), and text summary

    💡 **Tip**: Your results are saved in this session. You can download multiple times or start a new analysis using the button in the sidebar.
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
        submitted = st.form_submit_button("📥 Fetch Data", use_container_width=True)

    if submitted:
        st.session_state.extraction_username = username
        st.session_state.extraction_perimeter_raw = perimeter_raw
        perimeters = parse_perimeter_input(perimeter_raw)

        try:
            with st.spinner("Requesting API and saving CSV..."):
                _, payload = extract_data_via_proxy(username, password, perimeters)
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
            }
        )

        try:
            preview_df = pd.read_csv(result["download_path"]).head()
            st.markdown("**Preview of downloaded data (first 5 rows)**")
            st.dataframe(preview_df, use_container_width=True)
        except FileNotFoundError:
            st.warning("The saved CSV could not be found at the reported path. It may have been moved or deleted.")


def handle_analysis(api_key: Optional[str], uploaded_file) -> None:
    """Execute the risk metric analysis workflow."""
    if not api_key:
        st.error("⚠️ Please enter your Google API Key in the sidebar to enable AI analysis.")
        return
    if uploaded_file is None:
        st.error("⚠️ Please upload a CSV file.")
        return

    reset_analysis_state()
    st.session_state.uploaded_file_name = uploaded_file.name

    try:
        df = pd.read_csv(uploaded_file)
        logger.info("Loaded data frame from %s with shape %s", uploaded_file.name, df.shape)

        df["ValueDate"] = pd.to_datetime(df["ValueDate"])

        ordered_metrics = organize_metrics(df)
        logger.info("Organized %s metric(s)", len(ordered_metrics))
        st.success(f"✅ Loaded {len(df)} rows with {len(ordered_metrics)} risk metrics")

        metrics_analyses = []
        llm_requests: list[LLMRequest] = []

        for idx, metric in enumerate(ordered_metrics):
            logger.info("Processing metric %s (%s/%s)", metric, idx + 1, len(ordered_metrics))
            st.header(f"📊 {metric} Analysis")

            max_limit_col = f"{metric}_limMaxValue"
            min_limit_col = f"{metric}_limMinValue"
            max_limit = df[max_limit_col] if max_limit_col in df.columns else None
            min_limit = df[min_limit_col] if min_limit_col in df.columns else None

            metric_series = df[metric]
            stats, outliers = calculate_statistics(metric_series)
            breaches = check_limit_breaches(df, metric, max_limit, min_limit)

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
                outlier_dates = df.loc[outliers.index, "ValueDate"].dt.strftime("%Y-%m-%d").tolist()
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
                fig = create_plotly_chart(df, metric, stats, outliers, max_limit, min_limit)
                st.plotly_chart(fig, use_container_width=True)

            img_base64 = save_and_encode_image(fig, metric)
            has_limits = (max_limit is not None) or (min_limit is not None)
            prompt_text = create_llm_prompt(metric, stats, outliers, breaches, has_limits)

            st.subheader("🤖 AI-Generated Insights")
            insights_placeholder = st.empty()

            valid_count = metric_series.count()
            zero_ratio = (metric_series == 0).sum() / valid_count if valid_count else 0.0
            skip_llm = zero_ratio >= 0.95
            if skip_llm:
                logger.info(
                    "Skipping LLM analysis for %s due to low exposure (zero ratio %.2f)",
                    metric,
                    zero_ratio,
                )
                insight_text = "Low exposure, no insight"
                insights_placeholder.markdown(
                    f"""
                    <div style=\"background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 4px solid #6c757d;\">
                        {insight_text}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                insights_placeholder.info("🤖 Generating AI insights...")

            metrics_analyses.append(
                {
                    "metric": metric,
                    "stats": stats,
                    "outliers": outliers,
                    "outlier_dates": outlier_dates,
                    "breaches": breaches,
                    "insights": "Low exposure, no insight" if skip_llm else None,
                    "fig": fig,
                }
            )

            if not skip_llm:
                llm_requests.append(
                    {
                        "metric": metric,
                        "prompt_text": prompt_text,
                        "img_base64": img_base64,
                        "placeholder": insights_placeholder,
                        "analysis_index": len(metrics_analyses) - 1,
                    }
                )

            if idx < len(ordered_metrics) - 1:
                st.divider()

        if llm_requests:
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
                    placeholder.markdown(
                        f"""
                        <div style=\"background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 4px solid #1f77b4;\">
                            {insight.replace(chr(10), '<br><br>')}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                metrics_analyses[request["analysis_index"]]["insights"] = insight

        st.session_state.metrics_analyses = metrics_analyses

        if len(metrics_analyses) > 1:
            st.divider()
            st.header("📋 Risk Portfolio Summary")
            st.markdown("*Comprehensive risk analysis across all metrics*")

            with st.spinner("Generating portfolio-level risk insights..."):
                portfolio_summary = get_portfolio_summary(metrics_analyses)
                if portfolio_summary.startswith("Error generating"):
                    logger.error("Portfolio summary generation failed")
                else:
                    logger.info("Portfolio summary generation succeeded")

            st.markdown(
                f"""
                <div style=\"background-color: #e8f4f8; padding: 25px; border-radius: 10px; border-left: 5px solid #0066cc;\">
                    <h3 style=\"margin-top: 0; color: #0066cc;\">🎯 Strategic Risk Assessment</h3>
                    {portfolio_summary.replace(chr(10), '<br><br>')}
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.session_state.portfolio_summary = portfolio_summary

        st.session_state.analysis_completed = True
        st.success("✅ Analysis complete!")
        logger.info("Analysis completed successfully for %s", uploaded_file.name)

    except Exception as error:  # noqa: BLE001 - surface detailed error to user
        st.error(f"❌ Error processing file: {str(error)}")
        st.exception(error)
        logger.exception("Analysis failed due to unexpected error")


def run_app() -> None:
    """Main entry point for the Streamlit application."""
    setup_page()
    initialize_session_state()

    api_key, uploaded_file, analyze_button = render_sidebar()

    analysis_tab, extraction_tab = st.tabs(["Risk Metrics Analysis", "API Extraction"])

    with analysis_tab:
        if analyze_button:
            handle_analysis(api_key, uploaded_file)
        elif not st.session_state.analysis_completed:
            display_welcome_panel()

        if st.session_state.analysis_completed and st.session_state.metrics_analyses:
            render_export_options()

    with extraction_tab:
        render_extraction_tab()
