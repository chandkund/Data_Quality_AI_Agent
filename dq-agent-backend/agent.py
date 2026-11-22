"""LLM agent with Gemini, Groq, and OpenRouter function-calling providers."""

import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types

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


load_dotenv(Path(__file__).with_name(".env"))

MODEL = "gemini-3.8-flash"
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
SYSTEM_INSTRUCTION = (
    "You are a data quality analyst. Call the tools to inspect the dataset, "
    "then report real issues only. Do not invent issues. Use each column's exact "
    "name from the dataset summary; never put a sample value in the column field. "
    "Describe statistical outliers using the tool's bounds and examples. Do not "
    "make medical or domain-specific claims unless a tool explicitly verifies them."
)
FINAL_JSON_REQUEST = """Return the final report as JSON only, with this exact shape:
{"score": 0-100, "summary": "One sentence naming the biggest confirmed data quality problem.", "issues": [{"column": "", "problem": "", "severity": "low|medium|high", "fix": ""}]}
Use only issues supported by the tool results. The summary must describe the most important confirmed issue, or say no issues were found. Do not include markdown fences or extra text."""

# Each tool accepts the short summary as context; the local implementation inspects df.
_SUMMARY_PARAMETER = {
    "type": "STRING",
    "description": "Short dataset summary already provided; never include the full dataset.",
}

TOOL_DECLARATIONS = [
    {
        "name": "check_nulls",
        "description": "Count null values and report their percentage in each affected column.",
    },
    {
        "name": "find_duplicates",
        "description": "Find duplicate rows and return a count with a few small examples.",
    },
    {
        "name": "detect_outliers",
        "description": "Find numeric outliers using the 1.5 times IQR rule.",
    },
    {
        "name": "check_types",
        "description": "Find mixed or unexpected types, including text in numeric columns.",
    },
    {
        "name": "check_value_rules",
        "description": "Find negative values in relevant columns and invalid date values.",
    },
    {
        "name": "check_placeholders",
        "description": "Find placeholder strings such as ?, unknown, N/A, none, -, null, or blanks.",
    },
    {
        "name": "check_text_consistency",
        "description": "Find surrounding spaces and values that differ only by letter case.",
    },
    {
        "name": "check_column_health",
        "description": "Find constant columns, columns over 50% null, and high-cardinality text columns.",
    },
]

_TOOL_FUNCTIONS = {
    "check_nulls": check_nulls,
    "find_duplicates": find_duplicates,
    "detect_outliers": detect_outliers,
    "check_types": check_types,
    "check_value_rules": check_value_rules,
    "check_placeholders": check_placeholders,
    "check_text_consistency": check_text_consistency,
    "check_column_health": check_column_health,
}

_FUNCTION_DECLARATIONS = [
    types.FunctionDeclaration(
        name=tool["name"],
        description=tool["description"],
        parameters={
            "type": "OBJECT",
            "properties": {"dataset_summary": _SUMMARY_PARAMETER},
        },
    )
    for tool in TOOL_DECLARATIONS
]


def _json_safe(value):
    """Convert pandas/numpy values to plain values before sending them to Gemini."""
    if value is None or value is pd.NA:
        return None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        value = value.item()
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _build_summary(df):
    """Build compact context; never serialize the full DataFrame."""
    return {
        "row_count": int(len(df)),
        "column_names": [str(column) for column in df.columns],
        "dtypes": {str(column): str(dtype) for column, dtype in df.dtypes.items()},
        "first_5_rows": _json_safe(df.head(5).to_dict(orient="records")),
    }


def _generate_with_retry(client, **request):
    """Retry temporary Gemini throttling and availability errors a few times."""
    retryable_markers = (
        "429",
        "RESOURCE_EXHAUSTED",
        "500",
        "INTERNAL",
        "502",
        "503",
        "UNAVAILABLE",
        "504",
        "DEADLINE_EXCEEDED",
    )
    for attempt in range(3):
        try:
            return client.models.generate_content(**request)
        except Exception as error:
            message = str(error).upper()
            status = str(
                getattr(error, "status_code", None) or getattr(error, "code", "")
            ).upper()
            can_retry = any(marker in message or marker in status for marker in retryable_markers)
            if not can_retry or attempt == 2:
                raise
            time.sleep(2 ** attempt)


def _parse_final_answer(text, tools_used, valid_columns=None):
    """Parse the model's JSON response, allowing an optional markdown fence."""
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)

    try:
        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            raise ValueError("The response is not a JSON object")

        score = parsed.get("score", 0)
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            score = 0
        score = max(0, min(100, int(score)))

        issues = parsed.get("issues", [])
        if not isinstance(issues, list):
            issues = []
        summary = parsed.get("summary", "")
        if not isinstance(summary, str):
            summary = ""
        summary = " ".join(summary.split())[:300]

        # Never show a model-generated value as a column if it is not in the CSV.
        if valid_columns is not None:
            column_lookup = {str(column).casefold(): str(column) for column in valid_columns}
            checked_issues = []
            for issue in issues:
                if not isinstance(issue, dict) or issue.get("column") is None:
                    continue
                column = str(issue["column"]).strip()
                actual_column = column_lookup.get(column.casefold())
                if actual_column:
                    issue["column"] = actual_column
                elif column.casefold() != "all columns":
                    continue

                severity = str(issue.get("severity", "medium")).lower()
                if severity not in {"low", "medium", "high"}:
                    severity = "medium"
                checked_issues.append({
                    "column": issue["column"],
                    "problem": str(issue.get("problem", "")),
                    "severity": severity,
                    "fix": str(issue.get("fix", "")),
                })
                if len(checked_issues) == 10:
                    break

            if issues and not checked_issues:
                return {
                    "score": 0,
                    "issues": [],
                    "summary": "The model returned issues for columns that are not in the dataset.",
                    "tools_used": tools_used,
                    "error": "The model returned issues for columns not present in the dataset.",
                }
            issues = checked_issues
        if not summary:
            summary = (
                f"The analysis found {len(issues)} data quality issue(s)."
                if issues
                else "No data quality issues were confirmed by the analysis."
            )
        return {"score": score, "summary": summary, "issues": issues, "tools_used": tools_used}
    except (json.JSONDecodeError, ValueError, TypeError):
        return {
            "score": 0,
            "issues": [],
            "summary": "The model could not provide a valid report summary.",
            "tools_used": tools_used,
            "error": "The model did not return valid JSON.",
        }


def _chat_completion_request(provider, endpoint, api_key, payload):
    """Send one request to an OpenAI-compatible chat completions API."""
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{provider} API returned HTTP {error.code}: {message[:500]}") from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError(f"{provider} API request failed: {error}") from error


def _run_compatible_agent(df, api_key, tools_used, provider, endpoint, model):
    """Run local function tools through a compatible chat completions API."""
    summary = _build_summary(df)
    declarations = [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dataset_summary": {
                            "type": "string",
                            "description": "Short dataset summary already provided.",
                        }
                    }
                },
            },
        }
        for tool in TOOL_DECLARATIONS
    ]
    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": "Dataset summary:\n" + json.dumps(summary)},
    ]

    # Each round either runs requested local checks or returns a final answer.
    for _ in range(7):
        response = _chat_completion_request(provider, endpoint, api_key, {
            "model": model,
            "messages": messages,
            "tools": declarations,
            "tool_choice": "auto",
        })
        assistant_message = response["choices"][0]["message"]
        messages.append(assistant_message)
        calls = assistant_message.get("tool_calls", []) or []
        if not calls:
            break

        for tool_call in calls:
            function_call = tool_call.get("function", {})
            name = function_call.get("name", "")
            if name not in tools_used:
                tools_used.append(name)
            function = _TOOL_FUNCTIONS.get(name)
            result = function(df) if function else {"error": f"Unsupported tool: {name}"}
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": name,
                "content": json.dumps(_json_safe(result), ensure_ascii=False),
            })

    # Ask for a JSON-only answer after the tool loop (including its last results).
    messages.append({"role": "user", "content": FINAL_JSON_REQUEST})
    final_response = _chat_completion_request(provider, endpoint, api_key, {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_object"},
    })
    text = final_response["choices"][0]["message"].get("content", "")
    result = _parse_final_answer(text, tools_used, df.columns)
    if "error" not in result:
        result["provider"] = provider.lower()
    return result


def _run_groq_agent(df, api_key, tools_used):
    """Run the Groq fallback with the configured model."""
    return _run_compatible_agent(
        df,
        api_key,
        tools_used,
        "Groq",
        "https://api.groq.com/openai/v1/chat/completions",
        GROQ_MODEL,
    )


def _run_openrouter_agent(df, api_key, tools_used):
    """Run OpenRouter's free-model router after configured earlier providers fail."""
    return _run_compatible_agent(
        df,
        api_key,
        tools_used,
        "OpenRouter",
        "https://openrouter.ai/api/v1/chat/completions",
        OPENROUTER_MODEL,
    )


def _run_fallbacks(df, tools_used, primary_error=None):
    """Try Groq then OpenRouter, returning a report or a clear combined error."""
    fallbacks = [
        ("Groq", os.getenv("GROQ_API_KEY"), _run_groq_agent),
        ("OpenRouter", os.getenv("OPENROUTER_API_KEY"), _run_openrouter_agent),
    ]
    errors = []
    for name, api_key, run_provider in fallbacks:
        if not api_key:
            env_name = "GROQ_API_KEY" if name == "Groq" else "OPENROUTER_API_KEY"
            errors.append(f"{name} fallback skipped ({env_name} is not set in the backend process)")
            continue
        try:
            result = run_provider(df, api_key, tools_used)
            if "error" in result:
                raise RuntimeError(result["error"])
            return result
        except Exception as error:
            errors.append(f"{name} fallback failed ({error})")

    if primary_error:
        errors.append(f"Gemini primary failed ({primary_error})")
    if not errors:
        errors.append("Configure GEMINI_API_KEY, GROQ_API_KEY, or OPENROUTER_API_KEY.")
    return {
        "score": 0,
        "issues": [],
        "tools_used": tools_used,
        # List secondary providers first to keep their details visible in the UI.
        "error": "; ".join(errors),
    }


def run_agent(df) -> dict:
    """Inspect a DataFrame with Gemini or Groq and return a JSON-safe report."""
    tools_used = []
    api_key = os.getenv("GEMINI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key and not groq_key and not openrouter_key:
        return {
            "score": 0,
            "issues": [],
            "tools_used": tools_used,
            "error": "Configure GEMINI_API_KEY, GROQ_API_KEY, or OPENROUTER_API_KEY to run the analysis.",
        }

    # If Gemini is not configured, try the available fallback providers directly.
    if not api_key:
        return _run_fallbacks(df, tools_used)

    try:
        client = genai.Client(api_key=api_key)
        summary = _build_summary(df)
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text="Dataset summary:\n" + json.dumps(summary))],
            )
        ]
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[types.Tool(function_declarations=_FUNCTION_DECLARATIONS)],
        )

        # Reserve the eighth request for the final JSON answer.
        for _ in range(7):
            response = _generate_with_retry(
                client,
                model=MODEL,
                contents=contents,
                config=config,
            )
            if not response.candidates:
                break

            model_content = response.candidates[0].content
            function_calls = [
                part.function_call
                for part in model_content.parts
                if getattr(part, "function_call", None)
            ]
            contents.append(model_content)
            if not function_calls:
                break

            function_responses = []
            for call in function_calls:
                function_name = call.name
                if function_name not in tools_used:
                    tools_used.append(function_name)

                function = _TOOL_FUNCTIONS.get(function_name)
                if function is None:
                    result = {"error": f"Unsupported tool: {function_name}"}
                else:
                    result = function(df)

                function_responses.append(
                    types.Part.from_function_response(
                        name=function_name,
                        response=_json_safe(result),
                    )
                )

            contents.append(types.Content(role="user", parts=function_responses))

        # Ask for a strict JSON report after tool execution ends or reaches the limit.
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=FINAL_JSON_REQUEST)]))
        final_response = _generate_with_retry(
            client,
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
            ),
        )
        final_text = final_response.text if final_response else ""
        result = _parse_final_answer(final_text, tools_used, df.columns)
        if "error" in result and (groq_key or openrouter_key):
            return _run_fallbacks(df, tools_used, primary_error=result["error"])
        if "error" not in result:
            result["provider"] = "gemini"
        return result
    except Exception as error:
        if groq_key or openrouter_key:
            return _run_fallbacks(df, tools_used, primary_error=str(error))
        return _run_fallbacks(df, tools_used, primary_error=f"Gemini request failed: {error}")


if __name__ == "__main__":
    data_file = Path(__file__).parent / "data" / "dirty.csv"
    dataframe = pd.read_csv(data_file, keep_default_na=False, na_values=[""])
    print(json.dumps(run_agent(dataframe), indent=2, ensure_ascii=False))
