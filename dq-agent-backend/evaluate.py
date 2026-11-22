"""Measure direct tool recall and repeated Gemini-agent accuracy."""

import json
from pathlib import Path

import pandas as pd

from agent import run_agent
from tools import (
    check_column_health,
    check_nulls,
    check_placeholders,
    check_text_consistency,
    check_types,
    check_value_rules,
    detect_outliers,
    find_duplicates,
)


DATA_DIR = Path(__file__).parent / "data"
RESULTS_FILE = DATA_DIR / "evaluation_results.json"
TOOL_FUNCTIONS = [
    check_nulls,
    find_duplicates,
    detect_outliers,
    check_types,
    check_value_rules,
    check_placeholders,
    check_text_consistency,
    check_column_health,
]
ISSUE_KEYWORDS = {
    "random_nulls": ("null", "missing", "blank", "empty"),
    "duplicate_rows": ("duplicate",),
    "extreme_outliers": ("outlier", "extreme"),
    "text_in_numeric_column": ("type", "text", "placeholder", "non-numeric", "unknown"),
    "negative_values": ("negative", "invalid"),
    "whitespace": ("whitespace", "space", "trim", "inconsistent"),
    "case": ("case", "capitalization", "inconsistent"),
}


def issue_label(injected_issue):
    return f"{injected_issue['issue_type']} ({injected_issue.get('column', 'unknown')})"


def tool_detected_issue(tool_name, result, injected_issue):
    """Check whether a direct tool result contains evidence for one log entry."""
    if "error" in result:
        return False

    issue_type = injected_issue["issue_type"]
    column = str(injected_issue.get("column", ""))
    minimum_count = int(injected_issue.get("rows_affected", 1))
    details = result.get("details", {})

    if tool_name == "check_nulls" and issue_type == "random_nulls":
        return details.get("columns", {}).get(column, {}).get("null_count", 0) >= minimum_count

    if tool_name == "find_duplicates" and issue_type == "duplicate_rows":
        return details.get("duplicate_rows", 0) >= minimum_count

    if tool_name == "detect_outliers" and issue_type == "extreme_outliers":
        column_result = details.get("columns", {}).get(column)
        if not column_result:
            return False
        lower = column_result.get("lower_bound", float("-inf"))
        upper = column_result.get("upper_bound", float("inf"))
        # Check the injected values against the tool's IQR bounds, not its examples.
        injected_values = injected_issue.get("values", [])
        return any(value < lower or value > upper for value in injected_values)

    if tool_name == "check_types" and issue_type == "text_in_numeric_column":
        column_result = details.get("columns", {}).get(column, {})
        return column_result.get("non_numeric_values", 0) >= minimum_count

    if tool_name == "check_value_rules" and issue_type == "negative_values":
        column_result = details.get("negative_values", {}).get(column, {})
        return column_result.get("count", 0) >= minimum_count

    if tool_name == "check_placeholders" and issue_type == "text_in_numeric_column":
        column_result = details.get("columns", {}).get(column, {})
        examples = {str(value).strip().casefold() for value in column_result.get("examples", [])}
        expected_value = str(injected_issue.get("value", "unknown")).strip().casefold()
        return column_result.get("count", 0) >= minimum_count and expected_value in examples

    if tool_name == "check_text_consistency" and issue_type in {"whitespace", "case"}:
        column_result = details.get("columns", {}).get(column, {})
        if issue_type == "whitespace":
            return column_result.get("leading_or_trailing_space_count", 0) >= minimum_count
        return column_result.get("mixed_case_variant_groups", 0) > 0

    if tool_name == "check_column_health":
        column_result = details.get("columns", {}).get(column, {})
        if issue_type == "mostly_null_columns":
            return column_result.get("null_percent", 0) > 50
        if issue_type == "constant_columns":
            return column_result.get("constant", False)
        if issue_type == "high_cardinality_text_columns":
            return "high_cardinality_text" in column_result

    return False


def issue_matches_injection(issue, injected_issue):
    """Match an agent issue by column and a keyword related to its injected type."""
    if not isinstance(issue, dict):
        return False

    issue_type = injected_issue["issue_type"]
    column = str(injected_issue.get("column", "")).strip().casefold()
    issue_column = str(issue.get("column", "")).strip().casefold()
    issue_text = " ".join(str(value) for value in issue.values()).casefold()

    if column == "all columns":
        column_matches = issue_column in {
            "",
            "all columns",
            "dataset",
            "entire dataset",
            "rows",
        }
    else:
        column_matches = issue_column == column or column in issue_text

    keywords = ISSUE_KEYWORDS.get(issue_type, ())
    return column_matches and any(keyword in issue_text for keyword in keywords)


def evaluate_agent_report(report, injected_issues):
    """Calculate recall and precision for one agent response."""
    if report.get("error"):
        return {
            "found_issue_types": [],
            "missed_issue_types": [],
            "recall_found": None,
            "recall_total": len(injected_issues),
            "recall": None,
            "precision_matches": None,
            "precision_total": None,
            "precision": None,
            "total_issues": None,
            "unmatched_issues": [],
            "tools_used": report.get("tools_used", []),
            "agent_error": report["error"],
        }

    issues = report.get("issues", [])
    if not isinstance(issues, list):
        issues = []

    found_labels = []
    missed_labels = []
    for injected_issue in injected_issues:
        if any(issue_matches_injection(issue, injected_issue) for issue in issues):
            found_labels.append(issue_label(injected_issue))
        else:
            missed_labels.append(issue_label(injected_issue))

    matched_issue_indexes = [
        index
        for index, issue in enumerate(issues)
        if any(issue_matches_injection(issue, injected) for injected in injected_issues)
    ]
    unmatched_issues = [
        issue for index, issue in enumerate(issues) if index not in matched_issue_indexes
    ]
    precision = len(matched_issue_indexes) / len(issues) if issues else 0.0
    recall = len(found_labels) / len(injected_issues) if injected_issues else 0.0

    return {
        "found_issue_types": found_labels,
        "missed_issue_types": missed_labels,
        "recall_found": len(found_labels),
        "recall_total": len(injected_issues),
        "recall": recall,
        "precision_matches": len(matched_issue_indexes),
        "precision_total": len(issues),
        "precision": precision,
        "total_issues": len(issues),
        "unmatched_issues": unmatched_issues,
        "tools_used": report.get("tools_used", []),
        "agent_error": report.get("error"),
    }


def print_tool_level_results(tool_results, injected_issues):
    """Print the injected issue entries detected by each tool when run alone."""
    print("Tool-level recall (direct tool calls, no LLM):")
    for tool_name, result in tool_results.items():
        detected = [
            issue_label(injected)
            for injected in injected_issues
            if tool_detected_issue(tool_name, result, injected)
        ]
        print(f"  {tool_name}: {', '.join(detected) if detected else 'none'}")


def print_agent_results(run_results):
    """Print per-run recall and precision, then unmatched issues for review."""
    headings = ("Run", "Recall", "Precision", "Issues")
    rows = [
        (
            f"Run {result['run']}",
            f"{result['recall_found']}/{result['recall_total']}"
            if result["recall"] is not None
            else "N/A",
            f"{result['precision'] * 100:.1f}%"
            if result["precision"] is not None
            else "N/A",
            str(result["total_issues"])
            if result["total_issues"] is not None
            else "N/A",
        )
        for result in run_results
    ]
    widths = [max(len(headings[i]), *(len(row[i]) for row in rows)) for i in range(4)]
    print("\nAgent results:")
    print(" | ".join(headings[i].ljust(widths[i]) for i in range(4)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(row[i].ljust(widths[i]) for i in range(4)))

    for result in run_results:
        print(f"\nRun {result['run']} tools used: {', '.join(result['tools_used']) or 'none'}")
        if result["agent_error"]:
            print(f"  Agent error: {result['agent_error']}")
            print("  Accuracy metrics: not evaluated because the agent run failed")
            continue
        if result["unmatched_issues"]:
            print("  Unmatched issues for manual review:")
            for issue in result["unmatched_issues"]:
                print("  - " + json.dumps(issue, ensure_ascii=False))
        else:
            print("  Unmatched issues: none")


def main():
    dirty_df = pd.read_csv(DATA_DIR / "dirty.csv", keep_default_na=False, na_values=[""])
    clean_df = pd.read_csv(DATA_DIR / "clean.csv", keep_default_na=False, na_values=[""])
    with (DATA_DIR / "injected_log.json").open("r", encoding="utf-8") as log_file:
        injected_issues = json.load(log_file)

    # Run each tool once directly to measure tool-level recall without Gemini.
    tool_results = {
        tool.__name__: tool(dirty_df)
        for tool in TOOL_FUNCTIONS
    }
    print_tool_level_results(tool_results, injected_issues)

    # Run the full agent five times to account for variation in model tool selection.
    run_results = []
    for run_number in range(1, 6):
        report = run_agent(dirty_df)
        run_results.append({"run": run_number, **evaluate_agent_report(report, injected_issues)})

    print_agent_results(run_results)

    clean_report = run_agent(clean_df)
    clean_issues = clean_report.get("issues", [])
    if not isinstance(clean_issues, list):
        clean_issues = []
    false_alarm_count = None if clean_report.get("error") else len(clean_issues)
    print(
        "\nIssues reported on clean data: "
        f"{false_alarm_count if false_alarm_count is not None else 'N/A'}"
    )
    if clean_report.get("error"):
        print(f"Clean-data agent error: {clean_report['error']}")

    successful_runs = [result for result in run_results if result["recall"] is not None]
    average_recall_found = (
        sum(result["recall_found"] for result in successful_runs) / len(successful_runs)
        if successful_runs
        else None
    )
    average_precision = (
        sum(result["precision"] for result in successful_runs) / len(successful_runs)
        if successful_runs
        else None
    )

    results = {
        "tool_level_recall": {
            tool_name: {
                "issues_found": result.get("issues_found", False),
                "detected_issue_types": [
                    issue_label(injected)
                    for injected in injected_issues
                    if tool_detected_issue(tool_name, result, injected)
                ],
                "result": result,
            }
            for tool_name, result in tool_results.items()
        },
        "agent_runs": run_results,
        "clean_data_false_positive_check": {
            "issue_count": false_alarm_count,
            "issues": clean_issues,
            "agent_error": clean_report.get("error"),
        },
        "summary": {
            "average_recall_found": average_recall_found,
            "injected_issue_types": len(injected_issues),
            "successful_agent_runs": len(successful_runs),
            "attempted_agent_runs": len(run_results),
            "average_recall": average_recall_found / len(injected_issues)
            if injected_issues and average_recall_found is not None
            else None,
            "average_precision_percent": average_precision * 100
            if average_precision is not None
            else None,
            "false_alarms_on_clean_data": false_alarm_count,
        },
    }
    with RESULTS_FILE.open("w", encoding="utf-8") as result_file:
        json.dump(results, result_file, indent=2, ensure_ascii=False)
        result_file.write("\n")

    print(f"Saved results to: {RESULTS_FILE}")

    # Keep these as the final report lines for easy copy/paste.
    recall_text = f"{average_recall_found:.1f}" if average_recall_found is not None else "N/A"
    precision_text = f"{average_precision * 100:.1f}%" if average_precision is not None else "N/A"
    print(
        f"\nRecall: {recall_text} of {len(injected_issues)} injected issue types "
        f"(average over {len(successful_runs)} successful runs)"
    )
    print(f"Precision: {precision_text}")
    print(f"False alarms on clean data: {false_alarm_count if false_alarm_count is not None else 'N/A'}")


if __name__ == "__main__":
    main()
