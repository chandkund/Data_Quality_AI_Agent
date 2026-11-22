import Link from "next/link";
import { ArrowLeft, SearchX } from "lucide-react";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f4f9fd] px-5 text-center">
      <div className="max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-50 text-sky-700"><SearchX size={24} aria-hidden="true" /></span>
        <p className="mt-5 text-xs font-semibold uppercase tracking-[0.16em] text-sky-700">404 · Not found</p>
        <h1 className="mt-2 text-2xl font-semibold text-slate-900">This page isn’t here</h1>
        <p className="mt-2 text-sm leading-6 text-slate-600">The link may be outdated, or the page may have moved.</p>
        <Link href="/" className="mt-6 inline-flex items-center gap-2 rounded-xl bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-sky-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-600 focus-visible:ring-offset-2">
          <ArrowLeft size={16} aria-hidden="true" />Back to the analyzer
        </Link>
      </div>
    </main>
  );
}
