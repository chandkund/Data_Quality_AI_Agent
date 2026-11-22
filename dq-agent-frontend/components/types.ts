export type Severity = "low" | "medium" | "high";

export type Issue = {
  column: string;
  problem: string;
  severity: Severity | string;
  fix: string;
};

export type AnalysisReport = {
  score: number;
  issues: Issue[];
  tools_used: string[];
  rows?: number;
  columns?: number;
  summary?: string;
  error?: string;
};
