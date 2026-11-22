"use client";

import { useRef, useState } from "react";
import { motion } from "framer-motion";
import { FileSpreadsheet, FileUp, X } from "lucide-react";

const MAX_FILE_SIZE = 5 * 1024 * 1024;

type Props = {
  file: File | null;
  loading: boolean;
  onFile: (file: File | null) => void;
  onError: (message: string) => void;
  onAnalyze: () => void;
  onSample: () => void;
};

export function UploadCard({ file, loading, onFile, onError, onAnalyze, onSample }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function acceptFile(selected: File | undefined) {
    if (!selected) return;
    onError("");
    if (!selected.name.toLowerCase().endsWith(".csv")) {
      onFile(null);
      onError("That file type isn’t supported. Please choose a CSV file.");
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    if (selected.size > MAX_FILE_SIZE) {
      onFile(null);
      onError("That file is too large. Please choose a CSV smaller than 5 MB.");
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    onFile(selected);
  }

  function browse() {
    if (!loading) inputRef.current?.click();
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7" aria-label="Upload dataset">
      <input
        id="csv-file-input" ref={inputRef} type="file" accept=".csv,text/csv" className="sr-only"
        aria-label="Choose a CSV file" disabled={loading}
        onChange={(event) => acceptFile(event.target.files?.[0])}
      />
      <motion.div
        role="button" tabIndex={loading ? -1 : 0}
        aria-label="Upload a CSV file. Press Enter or Space to browse."
        aria-disabled={loading}
        onClick={browse}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            browse();
          }
        }}
        onDragOver={(event) => { event.preventDefault(); if (!loading) setDragging(true); }}
        onDragLeave={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false);
        }}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          if (!loading) acceptFile(event.dataTransfer.files?.[0]);
        }}
        animate={{ scale: dragging ? 1.01 : 1, borderColor: dragging ? "#0284c7" : "#cbd5e1", backgroundColor: dragging ? "#f0f9ff" : "#ffffff" }}
        transition={{ duration: 0.2 }}
        className={`cursor-pointer rounded-2xl border-2 border-dashed p-7 text-center outline-none transition-shadow focus-visible:ring-4 focus-visible:ring-sky-200 sm:p-10 ${dragging ? "shadow-md" : "hover:border-sky-400 hover:bg-sky-50/50"} ${loading ? "pointer-events-none opacity-60" : ""}`}
      >
        <div className={`mx-auto flex h-14 w-14 items-center justify-center rounded-2xl ${dragging ? "bg-sky-100 text-sky-800" : "bg-slate-100 text-slate-600"}`}>
          <FileUp size={25} aria-hidden="true" />
        </div>
        <p className="mt-4 text-base font-semibold text-slate-900">Drag your CSV here or click to browse</p>
        <p className="mt-1 text-sm text-slate-500">CSV only · Maximum file size 5 MB</p>
      </motion.div>

      {file && (
        <div className="mt-4 flex items-center gap-3 rounded-xl border border-sky-100 bg-sky-50/70 px-4 py-3">
          <FileSpreadsheet size={19} className="shrink-0 text-sky-700" aria-hidden="true" />
          <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-800">{file.name}</span>
          <span className="shrink-0 text-xs text-slate-500">{(file.size / 1024).toFixed(0)} KB</span>
          <button type="button" aria-label="Remove selected CSV" onClick={() => { onFile(null); if (inputRef.current) inputRef.current.value = ""; }}
            className="rounded-lg p-1.5 text-slate-500 hover:bg-white hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-600">
            <X size={16} aria-hidden="true" />
          </button>
        </div>
      )}

      <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:justify-end">
        <motion.button type="button" whileHover={loading ? undefined : { y: -1 }} whileTap={loading ? undefined : { scale: 0.98 }}
          onClick={onSample} disabled={loading}
          className="inline-flex min-h-11 items-center justify-center rounded-xl border border-slate-300 bg-white px-5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">
          Try sample dataset
        </motion.button>
        <motion.button type="button" whileHover={loading || !file ? undefined : { y: -1 }} whileTap={loading || !file ? undefined : { scale: 0.98 }}
          onClick={onAnalyze} disabled={loading || !file}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-sky-700 px-6 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-800 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none">
          Analyze dataset <span aria-hidden="true">→</span>
        </motion.button>
      </div>
    </section>
  );
}
