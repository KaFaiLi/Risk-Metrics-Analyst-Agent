from risk_metrics_app.reporting import metric_status, kpi_counts


def _analysis(metric, breaches, n_outliers):
    return {
        "metric": metric,
        "breaches": breaches,
        "outliers": list(range(n_outliers)),
    }


def test_metric_status_precedence():
    assert metric_status(_analysis("a", [{"type": "max"}], 5)) == "breach"
    assert metric_status(_analysis("b", [], 3)) == "outlier"
    assert metric_status(_analysis("c", [], 0)) == "ok"


def test_kpi_counts_aggregate():
    analyses = [
        _analysis("a", [{"type": "max"}], 5),
        _analysis("b", [], 3),
        _analysis("c", [], 0),
        _analysis("d", [], 0),
    ]
    counts = kpi_counts(analyses)
    assert counts == {"total": 4, "breach": 1, "outlier": 1, "ok": 2}
