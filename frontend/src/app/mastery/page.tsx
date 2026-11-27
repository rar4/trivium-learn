"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, Eye, FileText, RotateCcw, Sparkles } from "lucide-react";
import { completeReview, downloadMasteryReport, getMasteryDashboard, MasteryDashboard } from "@/lib/api";

/**
 * Post-hoc mastery view. It only lists work the learner has already mastered
 * and items already due for review — never future titles, totals or remaining
 * work counts (Fog-of-War contract).
 */
export default function MasteryPage() {
  const [data, setData] = useState<MasteryDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [en, setEn] = useState(false);
  const [revealed, setRevealed] = useState<Record<number, boolean>>({});
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(() => {
    getMasteryDashboard()
      .then((d) => { setData(d); setError(null); })
      .catch((e) => setError(e instanceof Error ? e.message : "Unavailable"));
  }, []);

  useEffect(() => {
    setEn(localStorage.getItem("trivium_ui_lang") === "en-US");
    load();
  }, [load]);

  async function review(itemId: number, passed: boolean) {
    setBusy(itemId);
    try {
      await completeReview(itemId, passed);
      setRevealed((r) => ({ ...r, [itemId]: false }));
      load();
      window.dispatchEvent(new CustomEvent("trivium:profile-updated"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Review failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="min-h-screen bg-[#09090b] text-white px-4 sm:px-8 py-8">
      <div className="max-w-4xl mx-auto space-y-8">
        <header className="flex items-center justify-between gap-4">
          <Link href="/" className="flex items-center gap-2 text-xs font-bold text-neutral-400 hover:text-white cursor-pointer">
            <ArrowLeft className="w-4 h-4" /> {en ? "Back" : "Voltar"}
          </Link>
          <span className="text-[10px] font-bold uppercase tracking-widest text-neutral-600">
            {en ? "Earned work only" : "Apenas trabalho concluído"}
          </span>
        </header>

        {error && <p className="text-sm text-red-400">{error}</p>}
        {!data && !error && <p className="text-sm text-neutral-500">{en ? "Loading..." : "Carregando..."}</p>}

        {data && (
          <>
            <section className="space-y-2">
              <h1 className="text-2xl sm:text-3xl font-black tracking-tight">
                {en ? "Mastery" : "Domínio"} <span className="text-[#ffe500]">·</span> {data.display_name}
              </h1>
              <div className="flex flex-wrap items-center gap-3 text-xs font-bold text-neutral-400">
                <span className="text-[#ffe500] flex items-center gap-1"><Sparkles className="w-3.5 h-3.5" />{data.xp} XP</span>
                <span>{en ? "Level" : "Nível"} {data.level}</span>
                <button
                  type="button"
                  id="download-mastery-report"
                  onClick={() => downloadMasteryReport().catch(() => setError(en ? "Report download failed." : "Falha ao baixar o relatório."))}
                  className="flex items-center gap-1.5 bg-[#18181b] hover:bg-[#222226] border border-[#2e2e33] text-white font-bold px-3 py-1.5 rounded-lg text-[11px] cursor-pointer"
                >
                  <FileText className="w-3.5 h-3.5 text-[#ffe500]" />
                  {en ? "Download report" : "Baixar relatório"}
                </button>
              </div>
            </section>

            <section className="space-y-3" data-testid="due-reviews">
              <h2 className="text-sm font-black uppercase tracking-widest text-neutral-500">
                {en ? "Due for review" : "Para revisar"}
              </h2>
              {data.reviewable_items.length === 0 && (
                <p className="text-xs text-neutral-600">{en ? "Nothing due right now." : "Nada para revisar agora."}</p>
              )}
              {data.reviewable_items.map((item) => (
                <article key={item.id} className="bg-[#141416] border border-[#27272a] rounded-xl p-4 space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded-full bg-[#27272a] text-neutral-300">
                      {item.kind === "mcq" ? (en ? "Question" : "Questão") : (en ? "Recall" : "Flashcard")}
                    </span>
                    <span className="text-[10px] text-neutral-600">{item.due_on}</span>
                  </div>
                  <p className="text-sm text-neutral-200">{item.prompt}</p>
                  {revealed[item.id] ? (
                    <p className="text-sm font-bold text-[#ffe500]">{item.expected}</p>
                  ) : (
                    <button type="button" onClick={() => setRevealed((r) => ({ ...r, [item.id]: true }))}
                      className="flex items-center gap-1.5 text-[11px] font-bold text-neutral-400 hover:text-white cursor-pointer">
                      <Eye className="w-3.5 h-3.5" /> {en ? "Reveal answer" : "Revelar resposta"}
                    </button>
                  )}
                  <div className="flex gap-2 pt-1">
                    <button type="button" disabled={busy === item.id} onClick={() => review(item.id, true)}
                      className="flex items-center gap-1.5 bg-[#ffe500] hover:bg-[#fff000] text-black font-extrabold text-[11px] px-3 py-1.5 rounded-lg cursor-pointer disabled:opacity-50">
                      <CheckCircle2 className="w-3.5 h-3.5" /> {en ? "Got it" : "Acertei"}
                    </button>
                    <button type="button" disabled={busy === item.id} onClick={() => review(item.id, false)}
                      className="flex items-center gap-1.5 bg-[#27272a] hover:bg-[#3f3f46] text-neutral-300 font-bold text-[11px] px-3 py-1.5 rounded-lg cursor-pointer disabled:opacity-50">
                      <RotateCcw className="w-3.5 h-3.5" /> {en ? "Again" : "De novo"}
                    </button>
                  </div>
                </article>
              ))}
            </section>

            <section className="space-y-3" data-testid="mastered-by-skill">
              <h2 className="text-sm font-black uppercase tracking-widest text-neutral-500">
                {en ? "Mastered by skill" : "Domínio por habilidade"}
              </h2>
              {data.mastered_by_skill.length === 0 && (
                <p className="text-xs text-neutral-600">{en ? "Your mastered steps will appear here." : "Seus passos concluídos aparecerão aqui."}</p>
              )}
              {data.mastered_by_skill.map((skill) => (
                <div key={skill.category} className="bg-[#141416] border border-[#27272a] rounded-xl p-4 space-y-2">
                  <h3 className="text-xs font-black uppercase text-[#ffe500]">{skill.category}</h3>
                  <ul className="space-y-2">
                    {skill.mastered_items.map((item) => (
                      <li key={item.id} className="text-xs text-neutral-300 border-l-2 border-[#3f3f46] pl-3">
                        <span className="font-bold text-white">{item.title}</span>
                        {item.course && <span className="text-neutral-600"> · {item.course}</span>}
                        {item.completed_on && <span className="block text-[10px] text-neutral-600">{item.completed_on}</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </section>
          </>
        )}
      </div>
    </main>
  );
}
