"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { AnimatePresence, motion, MotionConfig, useReducedMotion } from "framer-motion";
import { AlertTriangle, Check, Clipboard, Download, ExternalLink, ShieldCheck, Sparkles, Timer, Wrench } from "lucide-react";
import { IssuesTable } from "../components/IssuesTable";
import { LoadingSteps } from "../components/LoadingSteps";
import { ScoreGauge } from "../components/ScoreGauge";
import { StatCards } from "../components/StatCards";
import { ToolChips } from "../components/ToolChips";
import { UploadCard } from "../components/UploadCard";
import type { AnalysisReport } from "../components/types";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

function friendlyError(status: number, detail: string) {
  const message = detail.toLowerCase();
  if (status === 429) return "You’ve reached the request limit. Please wait a minute and try again.";
  if (status === 413 || message.includes("5 mb") || message.includes("file size")) return "That file is too large. Choose a CSV smaller than 5 MB.";
  if (message.includes("must be a csv") || message.includes(".csv file")) return "That file type isn’t supported. Please choose a CSV file.";
  if (status === 400) return "We couldn’t read that CSV. Check that it has a header and valid rows.";
  if (status >= 500) return "The analysis service ran into a problem. Please try again shortly.";
  return detail || "We couldn’t analyze that file. Please check it and try again.";
}

function friendlyAgentError(error: string) {
  const message = error.toLowerCase();
  const detail = error
    .replace(/Bearer\s+[A-Za-z0-9._-]+/gi, "Bearer [redacted]")
    .replace(/\b(?:gsk_|AIza)[A-Za-z0-9_-]+/g, "[redacted API key]")
    .replace(/(api[_ -]?key["'\s:=]+)[^\s,;]+/gi, "$1[redacted]")
    .replace(/[\r\n]+/g, " ")
    .trim()
    .slice(0, 700);
  if (message.includes("configure ")) return "Add an AI provider API key to the backend environment, then restart the backend.";
  if (message.includes("resource_exhausted") || message.includes("quota") || message.includes("429")) {
    return `AI provider quota is exhausted or rate-limited. Check provider details, then retry after the limit resets. ${detail}`;
  }
  if (message.includes("unauthorized") || message.includes("http 401") || message.includes("http 403") || message.includes("invalid api key")) {
    return `An AI provider rejected its API key. Check the backend keys. ${detail}`;
  }
  if (message.includes("socket") || message.includes("connection") || message.includes("urlopen")) {
    return "The backend couldn’t connect to an AI provider. Check the server’s internet access and API keys.";
  }
  return `The analysis agent failed: ${detail}`;
}

function ErrorBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} role="alert"
      className="flex flex-col gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-rose-900 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3"><AlertTriangle size={19} className="mt-0.5 shrink-0" aria-hidden="true" /><p className="text-sm leading-6">{message}</p></div>
      <button type="button" onClick={onRetry} className="shrink-0 rounded-xl border border-rose-300 bg-white px-4 py-2 text-sm font-semibold text-rose-800 hover:bg-rose-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-600">Try again</button>
    </motion.div>
  );
}

function LoadingSkeleton({ elapsed }: { elapsed: number }) {
  return <LoadingSteps elapsed={elapsed} />;
}

export default function HomePage() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [lastWasSample, setLastWasSample] = useState(false);
  const [copied, setCopied] = useState(false);
  const resultsRef = useRef<HTMLDivElement>(null);
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    if (!loading) return;
    const timer = window.setInterval(() => setElapsed((seconds) => seconds + 1), 1000);
    return () => window.clearInterval(timer);
  }, [loading]);

  useEffect(() => {
    if (!report) return;
    resultsRef.current?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  }, [reduceMotion, report]);

  const handleError = useCallback((message: string) => {
    setError(message);
    if (message) setReport(null);
  }, []);

  async function runAnalysis(useSample: boolean) {
    setLastWasSample(useSample);
    setError("");
    setReport(null);
    if (!useSample && !file) {
      setError("Choose a CSV file before starting the analysis.");
      return;
    }

    setLoading(true);
    setElapsed(0);
    try {
      let response: Response;
      if (useSample) {
        response = await fetch(`${API_BASE_URL}/sample`);
      } else {
        const formData = new FormData();
        formData.append("file", file as File);
        response = await fetch(`${API_BASE_URL}/analyze`, { method: "POST", body: formData });
      }

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(friendlyError(response.status, typeof payload.detail === "string" ? payload.detail : ""));
      }
      if (typeof payload.error === "string") throw new Error(friendlyAgentError(payload.error));
      setReport({
        ...payload,
        score: typeof payload.score === "number" ? payload.score : 0,
        issues: Array.isArray(payload.issues) ? payload.issues : [],
        tools_used: Array.isArray(payload.tools_used) ? payload.tools_used : [],
      } as AnalysisReport);
    } catch (requestError) {
      setError(requestError instanceof TypeError
        ? "Couldn’t reach the analysis server. Check that the backend is running, then try again."
        : requestError instanceof Error ? requestError.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function copySummary() {
    if (!report) return;
    const summary = report.summary || `Quality score ${report.score} out of 100 with ${report.issues.length} issue(s).`;
    try {
      await navigator.clipboard.writeText(summary);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setError("Couldn’t copy the summary. Your browser may block clipboard access.");
    }
  }

  function downloadReport() {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "data-quality-report.json";
    link.click();
    URL.revokeObjectURL(url);
  }

  function retry() {
    if (lastWasSample) void runAnalysis(true);
    else if (file) void runAnalysis(false);
    else {
      setError("");
      document.getElementById("csv-file-input")?.click();
    }
  }

  return (
    <MotionConfig reducedMotion="user">
      <main className="min-h-screen bg-[#f4f9fd] text-slate-900">
        <div className="mx-auto min-h-screen max-w-[1100px] px-4 sm:px-6 lg:px-8">
          <motion.header initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}
            className="flex h-[72px] items-center justify-between border-b border-slate-200/80">
            <a href="#top" className="flex items-center gap-2.5 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-600" aria-label="Data Quality Agent home">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-700 text-white"><ShieldCheck size={20} aria-hidden="true" /></span>
              <span className="text-sm font-semibold tracking-tight text-slate-900 sm:text-base">Data Quality Agent</span>
            </a>
            <a href="https://github.com/your-username/data-quality-ai-agent" target="_blank" rel="noreferrer" aria-label="View project on GitHub (placeholder link)"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-slate-400 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-600">
              <ExternalLink size={16} aria-hidden="true" /><span>GitHub</span>
            </a>
          </motion.header>

          <motion.section id="top" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08, duration: 0.4 }} className="pb-7 pt-10 sm:pb-9 sm:pt-14">
            <p className="mb-3 inline-flex items-center gap-2 rounded-full border border-sky-100 bg-white px-3 py-1 text-xs font-semibold text-sky-800"><Sparkles size={14} aria-hidden="true" /> DATA QUALITY, MADE CLEAR</p>
            <h1 className="max-w-3xl text-4xl font-semibold leading-[1.1] tracking-tight text-slate-950 sm:text-5xl lg:text-6xl">Find the issues hiding in your data.</h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600 sm:text-lg">Upload a CSV to uncover quality problems and get practical suggestions to fix them.</p>
            <div className="mt-6 flex flex-wrap gap-2.5">
              <FeatureChip icon={<Wrench size={14} />} text="8 analysis tools" />
              <FeatureChip icon={<ShieldCheck size={14} />} text="Files never stored" />
              <FeatureChip icon={<Timer size={14} />} text="Results in seconds" />
            </div>
          </motion.section>

          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.16, duration: 0.4 }}>
            <UploadCard file={file} loading={loading} onFile={setFile} onError={handleError}
              onAnalyze={() => void runAnalysis(false)} onSample={() => void runAnalysis(true)} />
          </motion.div>

          <div className="mt-5" aria-live="polite">
            <AnimatePresence mode="wait">
              {error && <ErrorBanner key="error" message={error} onRetry={retry} />}
              {!error && report && report.issues.length === 0 && <motion.div key="success" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-900"><Check size={16} className="mr-2 inline" aria-hidden="true" />Analysis complete. No issues were reported.</motion.div>}
            </AnimatePresence>
          </div>

          <section className="mt-6" aria-live="polite" aria-busy={loading}>
            {loading && <LoadingSkeleton elapsed={elapsed} />}
            {!loading && report && (
              <motion.div ref={resultsRef} className="scroll-mt-6 space-y-5 pb-10" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>
                <ScoreGauge score={report.score} summary={report.summary} />
                <StatCards report={report} />
                <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
                  <ActionButton onClick={() => void copySummary()} icon={copied ? <Check size={16} /> : <Clipboard size={16} />} label={copied ? "Copied" : "Copy summary"} />
                  <ActionButton onClick={downloadReport} icon={<Download size={16} />} label="Download report" primary />
                </div>
                <IssuesTable issues={report.issues} />
                <ToolChips tools={report.tools_used} />
              </motion.div>
            )}
          </section>

          <footer className="border-t border-slate-200 py-6 text-center text-xs leading-5 text-slate-500">
            <ShieldCheck size={14} className="mr-1 inline text-sky-700" aria-hidden="true" />Your uploaded file is analyzed in memory and isn’t saved by this app.
          </footer>
        </div>
      </main>
    </MotionConfig>
  );
}

function FeatureChip({ icon, text }: { icon: ReactNode; text: string }) {
  return <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm">{icon}{text}</span>;
}

function ActionButton({ onClick, icon, label, primary = false }: { onClick: () => void; icon: ReactNode; label: string; primary?: boolean }) {
  return <motion.button type="button" whileHover={{ y: -1 }} whileTap={{ scale: 0.98 }} onClick={onClick}
    className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-600 ${primary ? "bg-sky-700 text-white hover:bg-sky-800" : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"}`}>
    {icon}{label}
  </motion.button>;
}
