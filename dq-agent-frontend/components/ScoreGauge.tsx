"use client";

import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "framer-motion";
import { useEffect } from "react";

export function ScoreGauge({ score, summary }: { score: number; summary?: string }) {
  const reduceMotion = useReducedMotion();
  const value = useMotionValue(0);
  const displayed = useTransform(value, (latest) => Math.round(latest));
  const safeScore = Math.max(0, Math.min(100, score));
  const color = safeScore >= 80 ? "#16834a" : safeScore >= 50 ? "#c27a10" : "#d34242";
  const label = safeScore >= 80 ? "Excellent" : safeScore >= 50 ? "Needs attention" : "Poor";
  const circumference = 2 * Math.PI * 48;

  useEffect(() => {
    const animation = animate(value, safeScore, {
      duration: reduceMotion ? 0 : 0.55,
      ease: "easeOut",
    });
    return animation.stop;
  }, [reduceMotion, safeScore, value]);

  return (
    <motion.section
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4 }}
      className="flex flex-col items-center gap-5 rounded-2xl border border-sky-100 bg-white p-6 shadow-sm sm:flex-row sm:gap-7 sm:p-8"
      aria-label="Data quality score"
    >
      <div className="relative h-32 w-32 shrink-0" role="img" aria-label={`Score ${safeScore} out of 100`}>
        <svg viewBox="0 0 112 112" className="h-full w-full -rotate-90" aria-hidden="true">
          <circle cx="56" cy="56" r="48" fill="none" stroke="#e8efeb" strokeWidth="9" />
          <motion.circle
            cx="56" cy="56" r="48" fill="none" stroke={color} strokeWidth="9"
            strokeLinecap="round" strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: circumference * (1 - safeScore / 100) }}
            transition={{ duration: reduceMotion ? 0 : 0.55, ease: "easeOut" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <motion.span className="text-4xl font-bold tracking-tight text-slate-900">{displayed}</motion.span>
          <span className="text-xs font-medium text-slate-500">out of 100</span>
        </div>
      </div>
      <div className="text-center sm:text-left">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-700">Data quality score</p>
        <h2 className="mt-1 text-2xl font-semibold text-slate-900">{label}</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
          {summary || "Your analysis is complete. Review the findings and suggested fixes below."}
        </p>
      </div>
    </motion.section>
  );
}
