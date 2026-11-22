"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertCircle, AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, Filter } from "lucide-react";
import type { Issue } from "./types";

type FilterKey = "all" | "high" | "medium" | "low";
const ORDER: Record<string, number> = { high: 0, medium: 1, low: 2 };
const FILTERS: FilterKey[] = ["all", "high", "medium", "low"];

function SeverityBadge({ severity }: { severity: string }) {
  const level = severity.toLowerCase();
  const style = level === "high"
    ? "bg-rose-50 text-rose-700 ring-rose-200"
    : level === "medium"
      ? "bg-amber-50 text-amber-800 ring-amber-200"
      : "bg-emerald-50 text-emerald-800 ring-emerald-200";
  const Icon = level === "high" ? AlertTriangle : level === "medium" ? AlertCircle : CheckCircle2;
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold capitalize ring-1 ring-inset ${style}`}><Icon size={13} aria-hidden="true" />{level || "low"}</span>;
}

export function IssuesTable({ issues }: { issues: Issue[] }) {
  const [filter, setFilter] = useState<FilterKey>("all");
  const [expanded, setExpanded] = useState<number | null>(null);
  const filtered = useMemo(() => issues
    .map((issue, index) => ({ ...issue, sourceIndex: index }))
    .filter((issue) => filter === "all" || issue.severity.toLowerCase() === filter)
    .sort((a, b) => (ORDER[a.severity.toLowerCase()] ?? 3) - (ORDER[b.severity.toLowerCase()] ?? 3)), [filter, issues]);

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm" aria-label="Data quality issues">
      <div className="flex flex-col gap-4 border-b border-slate-100 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Issues found</h2>
          <p className="mt-1 text-sm text-slate-500">Select an issue to view its details and suggested fix.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter issues by severity">
          <Filter size={15} className="mr-1 text-slate-400" aria-hidden="true" />
          {FILTERS.map((item) => (
            <button key={item} type="button" aria-pressed={filter === item} onClick={() => setFilter(item)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold capitalize transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-600 ${filter === item ? "bg-sky-700 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
              {item === "all" ? "All" : item}
            </button>
          ))}
        </div>
      </div>

      {issues.length === 0 ? (
        <div className="px-6 py-12 text-center">
          <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 text-emerald-700"><CheckCircle2 size={25} aria-hidden="true" /></span>
          <h3 className="mt-4 text-base font-semibold text-slate-900">Your data looks good</h3>
          <p className="mt-1 text-sm text-slate-500">No data quality issues were reported for this dataset.</p>
        </div>
      ) : filtered.length === 0 ? (
        <p className="p-8 text-center text-sm text-slate-500">No issues match this severity filter.</p>
      ) : (
        <>
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full min-w-[700px] table-fixed text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr><th className="w-[20%] px-6 py-3 font-semibold">Column</th><th className="w-[45%] px-4 py-3 font-semibold">Problem</th><th className="w-[20%] px-4 py-3 font-semibold">Severity</th><th className="w-[15%] px-4 py-3 font-semibold">Details</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.map((issue, rowIndex) => {
                  const isOpen = expanded === issue.sourceIndex;
                  return (
                    <motion.tr key={issue.sourceIndex} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: rowIndex * 0.035, duration: 0.25 }}
                      onClick={() => setExpanded(isOpen ? null : issue.sourceIndex)}
                      onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setExpanded(isOpen ? null : issue.sourceIndex); } }}
                      tabIndex={0} role="button" aria-expanded={isOpen} aria-label={`${issue.column}: ${issue.problem}`} className="cursor-pointer outline-none hover:bg-sky-50/60 focus-visible:bg-sky-50/70">
                      <td className="px-6 py-4 font-semibold text-slate-900">{issue.column}</td>
                      <td className="px-4 py-4 leading-5 text-slate-600"><span className={isOpen ? "" : "line-clamp-2"}>{issue.problem}</span></td>
                      <td className="px-4 py-4"><SeverityBadge severity={issue.severity} /></td>
                      <td className="px-4 py-4 text-xs font-medium text-sky-800">{isOpen ? <span className="inline-flex items-center gap-1">Hide <ChevronUp size={14} /></span> : <span className="inline-flex items-center gap-1">View <ChevronDown size={14} /></span>}</td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </table>
            <AnimatePresence initial={false}>
              {expanded !== null && issues[expanded] && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.25 }} className="overflow-hidden border-t border-sky-100 bg-sky-50/60">
                  <div className="grid gap-4 p-5 sm:grid-cols-2 sm:px-6">
                    <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Full problem</p><p className="mt-1 text-sm leading-6 text-slate-700">{issues[expanded].problem}</p></div>
                    <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Suggested fix</p><p className="mt-1 text-sm leading-6 text-slate-700">{issues[expanded].fix}</p></div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <div className="space-y-3 p-4 md:hidden">
            {filtered.map((issue, rowIndex) => {
              const isOpen = expanded === issue.sourceIndex;
              return (
                <motion.article key={issue.sourceIndex} initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: rowIndex * 0.035, duration: 0.25 }} className="overflow-hidden rounded-xl border border-slate-200">
                  <button type="button" onClick={() => setExpanded(isOpen ? null : issue.sourceIndex)} aria-expanded={isOpen} className="w-full p-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-sky-600">
                    <div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-900">{issue.column}</p><p className="mt-1 line-clamp-3 text-sm leading-5 text-slate-600">{issue.problem}</p></div><SeverityBadge severity={issue.severity} /></div>
                    <span className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-sky-800">{isOpen ? "Hide details" : "View details"}{isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}</span>
                  </button>
                  <AnimatePresence initial={false}>
                    {isOpen && <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.25 }} className="overflow-hidden border-t border-slate-100 bg-slate-50 px-4 py-3">
                      <p className="text-xs font-semibold uppercase text-slate-500">Full problem</p><p className="mt-1 text-sm leading-6 text-slate-700">{issue.problem}</p>
                      <p className="mt-3 text-xs font-semibold uppercase text-slate-500">Suggested fix</p><p className="mt-1 text-sm leading-6 text-slate-700">{issue.fix}</p>
                    </motion.div>}
                  </AnimatePresence>
                </motion.article>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}
