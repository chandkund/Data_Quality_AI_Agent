import csv
import json
import random
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent
CLEAN_FILE = DATA_DIR / "clean.csv"
DIRTY_FILE = DATA_DIR / "dirty.csv"
LOG_FILE = DATA_DIR / "injected_log.json"
RANDOM_SEED = 42


def load_rows():
    """Read the clean dataset and preserve its column order."""
    with CLEAN_FILE.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file, skipinitialspace=True)
        columns = reader.fieldnames
        rows = list(reader)

    if not columns:
        raise ValueError(f"No CSV header found in {CLEAN_FILE}")

    required_columns = {
        "workclass",
        "education",
        "hours_per_week",
        "capital_gain",
        "age",
        "sex",
    }
    missing_columns = required_columns.difference(columns)
    if missing_columns:
        raise ValueError(f"clean.csv is missing columns: {sorted(missing_columns)}")
    if len(rows) < 50:
        raise ValueError("clean.csv must contain at least 50 rows")

    return columns, rows


def main():
    randomizer = random.Random(RANDOM_SEED)
    columns, clean_rows = load_rows()
    # Add a test-only constant column without changing clean.csv.
    if "country_code" not in columns:
        columns.append("country_code")
    for row in clean_rows:
        row["country_code"] = "IN"
    rows = [row.copy() for row in clean_rows]
    log = []

    # Protect these original rows so the 50 appended copies are exact duplicates.
    duplicate_source_indexes = set(randomizer.sample(range(len(clean_rows)), 50))
    duplicate_sources = [clean_rows[index] for index in duplicate_source_indexes]
    outlier_rows = randomizer.sample(
        [index for index in range(len(rows)) if index not in duplicate_source_indexes], 3
    )

    # Add nulls to 5% of the original rows in each requested column.
    null_count = round(len(clean_rows) * 0.05)
    for column in ("workclass", "education", "hours_per_week"):
        eligible_rows = [
            index
            for index, row in enumerate(rows)
            if index not in duplicate_source_indexes
            and not (column == "hours_per_week" and index in outlier_rows)
            # Preserve the dataset's original '?' values in workclass.
            and not (column == "workclass" and row[column].strip() == "?")
        ]
        if len(eligible_rows) < null_count:
            raise ValueError(f"Not enough eligible rows to inject nulls in {column}")

        for index in randomizer.sample(eligible_rows, null_count):
            rows[index][column] = ""

        log.append(
            {
                "issue_type": "random_nulls",
                "column": column,
                "rows_affected": null_count,
            }
        )

    # Use clearly extreme hours values so the injected outliers are easy to find.
    for index, value in zip(outlier_rows, (500, 600, 900)):
        rows[index]["hours_per_week"] = str(value)
    log.append(
        {
            "issue_type": "extreme_outliers",
            "column": "hours_per_week",
            "rows_affected": len(outlier_rows),
            "values": [500, 600, 900],
        }
    )

    unknown_rows = randomizer.sample(
        [index for index in range(len(rows)) if index not in duplicate_source_indexes], 20
    )
    for index in unknown_rows:
        rows[index]["capital_gain"] = "unknown"
    log.append(
        {
            "issue_type": "text_in_numeric_column",
            "column": "capital_gain",
            "rows_affected": len(unknown_rows),
            "value": "unknown",
        }
    )

    negative_age_rows = randomizer.sample(
        [index for index in range(len(rows)) if index not in duplicate_source_indexes], 15
    )
    for index in negative_age_rows:
        rows[index]["age"] = str(-abs(int(rows[index]["age"])))
    log.append(
        {
            "issue_type": "negative_values",
            "column": "age",
            "rows_affected": len(negative_age_rows),
        }
    )

    # Add spacing and case variants while leaving duplicate source rows untouched.
    sex_rows = [
        index for index, row in enumerate(rows)
        if index not in duplicate_source_indexes
        and row["sex"].strip().lower() in {"male", "female"}
    ]
    if len(sex_rows) < 40:
        raise ValueError("Not enough eligible rows to inject sex text inconsistencies")
    variants = {
        "male": (" Male", "MALE"),
        "female": ("Female ", "female"),
    }
    affected_sex_rows = randomizer.sample(sex_rows, 40)
    for index in affected_sex_rows:
        original = rows[index]["sex"].strip().lower()
        rows[index]["sex"] = randomizer.choice(variants[original])
    log.append(
        {
            "issue_type": "inconsistent_text",
            "column": "sex",
            "rows_affected": len(affected_sex_rows),
        }
    )

    # Append copies of clean rows to introduce exactly 50 duplicate records.
    rows.extend(row.copy() for row in duplicate_sources)
    log.append(
        {
            "issue_type": "duplicate_rows",
            "column": "all columns",
            "rows_affected": len(duplicate_sources),
        }
    )
    log.append(
        {
            "issue_type": "constant_column",
            "column": "country_code",
            "rows_affected": len(rows),
            "value": "IN",
        }
    )

    with DIRTY_FILE.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    with LOG_FILE.open("w", encoding="utf-8") as json_file:
        json.dump(log, json_file, indent=2)
        json_file.write("\n")

    print(f"Clean rows: {len(clean_rows)}")
    print(f"Dirty rows: {len(rows)} (includes 50 appended duplicates)")
    print("Injected issues:")
    for issue in log:
        print(
            f"  - {issue['issue_type']} in {issue['column']}: "
            f"{issue['rows_affected']} rows"
        )
    print(f"Saved dirty data to: {DIRTY_FILE}")
    print(f"Saved injection log to: {LOG_FILE}")


if __name__ == "__main__":
    main()
