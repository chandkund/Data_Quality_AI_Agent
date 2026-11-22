"use client";

import { motion } from "framer-motion";
import { Braces, CopyCheck, Database, FileCheck2, ScanSearch, ShieldCheck, TextSearch, Type } from "lucide-react";

const FRIENDLY_TOOLS: Record<string, { label: string; icon: typeof Database }> = {
  check_nulls: { label: "Null check", icon: ScanSearch },
  find_duplicates: { label: "Duplicate check", icon: CopyCheck },
  detect_outliers: { label: "Outlier detection", icon: ScanSearch },
  check_types: { label: "Type check", icon: Type },
  check_value_rules: { label: "Rule validation", icon: FileCheck2 },
  check_placeholders: { label: "Placeholder check", icon: Braces },
  check_text_consistency: { label: "Text consistency", icon: TextSearch },
  check_column_health: { label: "Column health", icon: ShieldCheck },
};

export function ToolChips({ tools }: { tools: string[] }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <h2 className="text-sm font-semibold text-slate-800">Analysis tools used</h2>
      <div className="mt-3 flex flex-wrap gap-2">
        {tools.length ? tools.map((tool, index) => {
          const item = FRIENDLY_TOOLS[tool];
          const Icon = item?.icon || Database;
          return (
            <motion.span key={tool} initial={{ opacity: 0, scale: 0.92 }} animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: index * 0.04, duration: 0.25 }}
              className="inline-flex items-center gap-1.5 rounded-full border border-sky-100 bg-sky-50 px-3 py-1.5 text-xs font-medium text-sky-800">
              <Icon size={13} aria-hidden="true" />{item?.label || tool.replace(/_/g, " ")}
            </motion.span>
          );
        }) : <p className="text-sm text-slate-500">No tool checks were reported.</p>}
      </div>
    </section>
  );
}
