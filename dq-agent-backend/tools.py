"""Small DataFrame checks for the Data Quality AI Agent."""

import json
from pathlib import Path

import pandas as pd
from pandas.api.types import is_numeric_dtype, is_object_dtype, is_string_dtype


def _plain(value):
    """Convert pandas/numpy scalars and missing values to JSON-safe values."""
    if value is None or value is pd.NA:
        return None
    if hasattr(value, "item"):
        value = value.item()
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _tool_result(name, issues_found, details):
    return {"tool": name, "issues_found": bool(issues_found), "details": details}


def _text_columns(df):
    return [
        column
        for column in df.columns
        if is_object_dtype(df[column].dtype) or is_string_dtype(df[column].dtype)
    ]


def check_nulls(df):
    """Report null counts and percentages for columns that contain nulls."""
    name = "check_nulls"
    try:
        columns = {}
        for column in df.columns:
            count = int(df[column].isna().sum())
            if count:
                columns[str(column)] = {
                    "null_count": count,
                    "null_percent": round(count / len(df) * 100, 2) if len(df) else 0.0,
                }
                if len(columns) == 10:
                    break
        return _tool_result(name, bool(columns), {"columns": columns})
    except Exception as error:
        return {"tool": name, "error": str(error)}


def find_duplicates(df):
    """Count duplicate rows and show up to five small examples."""
    name = "find_duplicates"
    try:
        duplicate_mask = df.duplicated(keep="first")
        duplicate_count = int(duplicate_mask.sum())
        example_columns = list(df.columns[:3])
        examples = []
        for index, row in df.loc[duplicate_mask].head(5).iterrows():
            examples.append(
                {
                    "index": _plain(index),
                    "values": {str(col): _plain(row[col]) for col in example_columns},
                }
            )
        return _tool_result(
            name,
            duplicate_count > 0,
            {"duplicate_rows": duplicate_count, "examples": examples},
        )
    except Exception as error:
        return {"tool": name, "error": str(error)}


def detect_outliers(df):
    """Find numeric outliers using the 1.5 x IQR rule."""
    name = "detect_outliers"
    try:
        columns = {}
        for column in df.select_dtypes(include="number").columns:
            values = df[column].dropna()
            if values.empty:
                continue
            q1 = float(values.quantile(0.25))
            q3 = float(values.quantile(0.75))
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            outliers = values[(values < lower) | (values > upper)]
            if not outliers.empty:
                columns[str(column)] = {
                    "count": int(len(outliers)),
                    "lower_bound": lower,
                    "upper_bound": upper,
                    "example_values": [_plain(value) for value in outliers.head(3)],
                }
                if len(columns) == 10:
                    break
        return _tool_result(name, bool(columns), {"columns": columns})
    except Exception as error:
        return {"tool": name, "error": str(error)}


def check_types(df):
    """Find mixed text/numeric columns and numeric values stored as text."""
    name = "check_types"
    try:
        columns = {}
        for column in df.columns:
            series = df[column].dropna()
            if series.empty:
                continue

            # Object columns can contain a numeric field mixed with text such as "unknown".
            if is_object_dtype(df[column].dtype) or is_string_dtype(df[column].dtype):
                text = series.astype("string").str.strip()
                candidates = text[text.ne("")]
                numeric = pd.to_numeric(candidates, errors="coerce")
                numeric_count = int(numeric.notna().sum())
                candidate_count = int(len(candidates))
                ratio = numeric_count / candidate_count if candidate_count else 0
                if ratio >= 0.8:
                    invalid = candidates[numeric.isna()]
                    columns[str(column)] = {
                        "issue": "mixed_numeric_and_text" if len(invalid) else "numeric_stored_as_text",
                        "numeric_values": numeric_count,
                        "non_numeric_values": int(len(invalid)),
                        "examples": [_plain(value) for value in invalid.drop_duplicates().head(5)]
                        if len(invalid)
                        else [],
                    }
                else:
                    type_names = sorted({type(value).__name__ for value in series})
                    if len(type_names) > 1:
                        columns[str(column)] = {
                            "issue": "mixed_python_types",
                            "types": type_names[:5],
                        }

            if len(columns) == 10:
                break

        return _tool_result(name, bool(columns), {"columns": columns})
    except Exception as error:
        return {"tool": name, "error": str(error)}


def check_value_rules(df):
    """Find negative values in relevant numeric columns and invalid dates."""
    name = "check_value_rules"
    try:
        negative_columns = {}
        date_columns = {}
        for column in df.columns:
            column_name = str(column).lower()
            if is_numeric_dtype(df[column].dtype) and any(
                word in column_name for word in ("age", "price", "amount", "salary", "gain", "hours")
            ):
                negatives = df.loc[df[column] < 0, column].dropna()
                if not negatives.empty:
                    negative_columns[str(column)] = {
                        "count": int(len(negatives)),
                        "example_values": [_plain(value) for value in negatives.head(5)],
                    }
                    if len(negative_columns) == 10:
                        break

        for column in df.columns:
            column_name = str(column).lower()
            if any(word in column_name for word in ("date", "time", "timestamp", "dob")):
                values = df[column].dropna().astype("string").str.strip()
                values = values[values.ne("")]
                parsed = pd.to_datetime(values, errors="coerce")
                invalid = values[parsed.isna()]
                if not invalid.empty:
                    date_columns[str(column)] = {
                        "invalid_count": int(len(invalid)),
                        "examples": [_plain(value) for value in invalid.drop_duplicates().head(5)],
                    }
                    if len(set(negative_columns) | set(date_columns)) >= 10:
                        break

        # Keep the combined result within the ten-column output limit.
        allowed_columns = list(dict.fromkeys([*negative_columns, *date_columns]))[:10]
        negative_columns = {
            column: details for column, details in negative_columns.items() if column in allowed_columns
        }
        date_columns = {
            column: details for column, details in date_columns.items() if column in allowed_columns
        }
        found = bool(negative_columns or date_columns)
        return _tool_result(
            name,
            found,
            {"negative_values": negative_columns, "invalid_dates": date_columns},
        )
    except Exception as error:
        return {"tool": name, "error": str(error)}


def check_placeholders(df):
    """Count common text placeholders used to represent missing values."""
    name = "check_placeholders"
    try:
        placeholders = {"?", "unknown", "n/a", "none", "-", "null", ""}
        columns = {}
        for column in _text_columns(df):
            text = df[column].astype("string").str.strip().str.casefold()
            matches = text.isin(placeholders)
            count = int(matches.sum())
            if count:
                examples = df.loc[matches, column].drop_duplicates().head(5)
                columns[str(column)] = {
                    "count": count,
                    "examples": [_plain(value) for value in examples],
                }
                if len(columns) == 10:
                    break
        return _tool_result(name, bool(columns), {"columns": columns})
    except Exception as error:
        return {"tool": name, "error": str(error)}


def check_text_consistency(df):
    """Find whitespace around text and values that differ only by letter case."""
    name = "check_text_consistency"
    try:
        columns = {}
        for column in _text_columns(df):
            raw = df[column].dropna().astype("string")
            trimmed = raw.str.strip()
            whitespace_mask = raw.ne(trimmed)
            variants = {}
            for value in trimmed.drop_duplicates():
                if value:
                    variants.setdefault(value.casefold(), set()).add(str(value))
            case_variants = [sorted(values) for values in variants.values() if len(values) > 1]
            if whitespace_mask.any() or case_variants:
                whitespace_examples = raw[whitespace_mask].drop_duplicates().head(5)
                columns[str(column)] = {
                    "leading_or_trailing_space_count": int(whitespace_mask.sum()),
                    "space_examples": [_plain(value) for value in whitespace_examples],
                    "mixed_case_variant_groups": len(case_variants),
                    "case_examples": [variants[:5] for variants in case_variants[:5]],
                }
                if len(columns) == 10:
                    break
        return _tool_result(name, bool(columns), {"columns": columns})
    except Exception as error:
        return {"tool": name, "error": str(error)}


def check_column_health(df):
    """Find constant, mostly-null, and high-cardinality text columns."""
    name = "check_column_health"
    try:
        columns = {}
        for column in df.columns:
            series = df[column]
            if series.nunique(dropna=True) <= 1:
                columns[str(column)] = {"constant": True}
                if len(columns) == 10:
                    break

        for column in df.columns:
            if str(column) in columns or len(columns) == 10:
                continue
            null_percent = float(df[column].isna().mean() * 100) if len(df) else 0.0
            if null_percent > 50:
                columns[str(column)] = {"null_percent": round(null_percent, 2)}

        for column in _text_columns(df):
            if str(column) in columns or len(columns) == 10:
                continue
            values = df[column].dropna()
            unique_count = int(values.nunique())
            unique_ratio = unique_count / len(values) if len(values) else 0
            # Require at least 20 values and a 90% unique ratio to avoid tiny columns.
            if len(values) >= 20 and unique_ratio >= 0.9:
                columns[str(column)] = {
                    "high_cardinality_text": {
                        "unique_count": unique_count,
                        "unique_percent": round(unique_ratio * 100, 2),
                    }
                }

        details = {
            "columns": columns,
            "high_cardinality_threshold": "at least 20 non-null values and 90% unique",
        }
        found = bool(columns)
        return _tool_result(name, found, details)
    except Exception as error:
        return {"tool": name, "error": str(error)}


if __name__ == "__main__":
    # Run every check on the generated sample data when this file is executed directly.
    data_file = Path(__file__).parent / "data" / "dirty.csv"
    dataframe = pd.read_csv(data_file, keep_default_na=False, na_values=[""])
    tools = [
        check_nulls,
        find_duplicates,
        detect_outliers,
        check_types,
        check_value_rules,
        check_placeholders,
        check_text_consistency,
        check_column_health,
    ]
    for tool in tools:
        print(json.dumps(tool(dataframe), indent=2, ensure_ascii=False))
