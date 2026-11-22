"use client";

import { motion } from "framer-motion";
import { AlertCircle, AlertTriangle, CircleCheck, Columns3, Rows3 } from "lucide-react";
import type { AnalysisReport } from "./types";

export function StatCards({ report }: { report: AnalysisReport }) {
  const count = (severity: string) => report.issues.filter((issue) => issue.severity.toLowerCase() === severity).length;
  const stats = [
    { label: "Total issues", value: report.issues.length, icon: AlertCircle, color: "text-slate-700", dot: "bg-slate-400" },
    { label: "High", value: count("high"), icon: AlertTriangle, color: "text-rose-700", dot: "bg-rose-500" },
    { label: "Medium", value: count("medium"), icon: AlertCircle, color: "text-amber-700", dot: "bg-amber-500" },
    { label: "Low", value: count("low"), icon: CircleCheck, color: "text-emerald-700", dot: "bg-emerald-500" },
    ...(typeof report.rows === "number" ? [{ label: "Rows", value: report.rows, icon: Rows3, color: "text-slate-700", dot: "bg-slate-400" }] : []),
    ...(typeof report.columns === "number" ? [{ label: "Columns", value: report.columns, icon: Columns3, color: "text-slate-700", dot: "bg-slate-400" }] : []),
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6" aria-label="Issue statistics">
      {stats.map(({ label, value, icon: Icon, color, dot }, index) => (
        <motion.div
          key={label} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.05, duration: 0.3 }}
          className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-medium text-slate-500">{label}</span>
            <Icon size={16} aria-hidden="true" className={color} />
          </div>
          <p className="mt-2 flex items-center gap-2 text-2xl font-semibold tabular-nums text-slate-900">
            <span className={`h-2 w-2 rounded-full ${dot}`} />{value.toLocaleString()}
          </p>
        </motion.div>
      ))}
    </div>
  );
}
