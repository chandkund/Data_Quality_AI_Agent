"use client";

import { motion } from "framer-motion";
import { Check, Circle, LoaderCircle } from "lucide-react";

const STEPS = [
  "Reading your file",
  "Checking missing values and duplicates",
  "Looking for outliers",
  "Validating data types and rules",
  "Writing the report",
];

export function LoadingSteps({ elapsed }: { elapsed: number }) {
  const activeStep = Math.min(Math.floor(elapsed / 3), STEPS.length - 1);

  return (
    <section className="space-y-5" role="status" aria-live="polite" aria-label="Analysis in progress">
      <div className="grid gap-5 md:grid-cols-[0.85fr_1.15fr]">
        <div className="flex min-h-48 items-center gap-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="skeleton-shimmer h-32 w-32 shrink-0 rounded-full" />
          <div className="flex-1 space-y-3">
            <div className="skeleton-shimmer h-3 w-28 rounded" />
            <div className="skeleton-shimmer h-7 w-36 rounded" />
            <div className="skeleton-shimmer h-3 w-full rounded" />
            <div className="skeleton-shimmer h-3 w-4/5 rounded" />
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="skeleton-shimmer mb-5 h-4 w-40 rounded" />
          <div className="space-y-4">
            {[0, 1, 2, 3].map((item) => (
              <div key={item} className="flex items-center gap-4">
                <div className="skeleton-shimmer h-4 w-4 rounded-full" />
                <div className="skeleton-shimmer h-4 flex-1 rounded" />
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Running quality checks</h2>
            <p className="mt-1 text-xs text-slate-500">This usually takes a few seconds.</p>
          </div>
          <span className="rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold tabular-nums text-sky-800">{elapsed}s</span>
        </div>
        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {STEPS.map((step, index) => {
            const done = index < activeStep;
            const active = index === activeStep;
            return (
              <li key={step} className={`flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm ${active ? "bg-sky-50 font-medium text-sky-900" : done ? "text-emerald-800" : "text-slate-400"}`}>
                {done ? <Check size={16} aria-label="Complete" /> : active ? <LoaderCircle size={16} className="animate-spin" aria-label="In progress" /> : <Circle size={16} aria-hidden="true" />}
                <span>{step}</span>
              </li>
            );
          })}
        </ol>
        {elapsed >= 20 && (
          <motion.p initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="mt-4 text-xs text-slate-500">
            The server may be waking up, this can take up to a minute.
          </motion.p>
        )}
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 p-5 sm:p-6"><div className="skeleton-shimmer h-5 w-36 rounded" /></div>
        <div className="space-y-3 p-5 sm:p-6">
          {[0, 1, 2].map((item) => <div key={item} className="skeleton-shimmer h-12 rounded-xl" />)}
        </div>
      </div>
    </section>
  );
}
