"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { getCourse, getNextStep, getCurrentStep, getCertificate, deleteCourse, CourseSummary, NextStepResponse, CurrentStepResponse, CertificateData } from "@/lib/api";
import { ArrowLeft, Play, CheckCircle2, Trash2, AlertTriangle, X, Settings, ShieldCheck, ChevronDown, ChevronUp, Award, EyeOff, Clock, Sparkles } from "lucide-react";
import Link from "next/link";
import SettingsModal from "@/components/SettingsModal";
import GamificationPanel from "@/components/GamificationPanel";
import { translations, SupportedLanguage, formatCourseLevel } from "@/lib/i18n";

const STAGE_LABELS: Record<string, { en: string; pt: string }> = {
  learn: { en: "Learn", pt: "Aprender" },
  quiz: { en: "Grammar gate", pt: "Portão da Gramática" },
  simulate: { en: "Logic gate", pt: "Portão da Lógica" },
  teach_back: { en: "Teach-back duel", pt: "Duelo de ensino" },
  unlock: { en: "Ready to unlock", pt: "Pronto para desbloquear" },
};

export default function CoursePage() {
  const params = useParams();
  const router = useRouter();
  const courseId = Number(params?.id);

  const [course, setCourse] = useState<CourseSummary | null>(null);
  const [nextStep, setNextStep] = useState<NextStepResponse | null>(null);
  const [currentStep, setCurrentStep] = useState<CurrentStepResponse | null>(null);
  const [justRevealed, setJustRevealed] = useState(false);
  const [certificate, setCertificate] = useState<CertificateData | null>(null);
  const [loading, setLoading] = useState(true);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showSourcesDossier, setShowSourcesDossier] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    if (!courseId) return;
    // Only the current-step endpoint carries the revealed title/hook. The
    // next-step endpoint is a blind pointer and must never be used for the card.
    setJustRevealed(new URLSearchParams(window.location.search).get("revealed") === "1");
    Promise.all([
      getCourse(courseId).catch(() => null),
      getNextStep(courseId).catch(() => null),
      getCurrentStep(courseId).catch(() => null),
      getCertificate(courseId).catch(() => null),
    ]).then(([c, ns, cs, cert]) => {
      setCourse(c);
      setNextStep(ns);
      setCurrentStep(cs);
      setCertificate(cert);
      setLoading(false);
    });
  }, [courseId]);

  const fallbackLang: SupportedLanguage = typeof window !== "undefined" && localStorage.getItem("trivium_ui_lang") === "en-US" ? "en-US" : "pt-BR";
  const lang: SupportedLanguage = course?.language === "en-US" ? "en-US" : fallbackLang;
  const t = translations[lang];
  const en = lang === "en-US";

  const handleDeleteCourse = async () => {
    if (!courseId) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await deleteCourse(courseId);
      router.push("/");
    } catch (err: unknown) {
      setDeleteError(err instanceof Error ? err.message : "Erro ao excluir o curso");
      setIsDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0b0b0b] text-white flex items-center justify-center">
        <div className="flex items-center space-x-3 text-[#ffe500] font-bold">
          <div className="w-5 h-5 border-2 border-[#ffe500] border-t-transparent rounded-full animate-spin" />
          <span>{t.course_loading_matrix}</span>
        </div>
      </div>
    );
  }

  if (!course) {
    return (
      <div className="min-h-screen bg-[#0b0b0b] text-white flex flex-col items-center justify-center p-6">
        <h2 className="text-2xl font-black mb-4">{t.course_not_found}</h2>
        <Link href="/" className="text-[#ffe500] font-bold flex items-center space-x-2">
          <ArrowLeft className="w-4 h-4" />
          <span>{t.course_back_home}</span>
        </Link>
      </div>
    );
  }

  const completed = nextStep?.completed_lessons ?? course.completed_lessons ?? [];
  const current = currentStep?.id ? currentStep : null;
  const stageLabel = STAGE_LABELS[current?.stage ?? "learn"] ?? STAGE_LABELS.learn;

  return (
    <main className="min-h-screen bg-[#0b0b0b] text-[#f4f4f5] pb-20">
      <header className="border-b border-[#1f1f23] px-4 sm:px-8 py-5 flex justify-between items-center bg-[#0e0e10]/80 backdrop-blur-md sticky top-0 z-40">
        <div className="flex items-center space-x-4">
          <Link href="/" className="flex items-center space-x-2.5 group">
            <div className="w-8 h-8 rounded-xl bg-[#141416] border border-[#ffe500]/40 flex items-center justify-center group-hover:border-[#ffe500] transition-all overflow-hidden p-1">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/trivium-logo.png" alt="Trivium Logo" className="w-full h-full object-contain" />
            </div>
            <span className="hidden sm:inline text-xs font-extrabold text-[#ffe500] uppercase tracking-widest">TRIVIUM</span>
          </Link>
          <span className="text-neutral-700 hidden sm:inline">|</span>
          <Link href="/" className="flex items-center space-x-1.5 text-xs font-bold text-neutral-400 hover:text-white transition-all">
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>{t.course_back_search}</span>
          </Link>
        </div>
        <div className="flex items-center space-x-3">
          <GamificationPanel compact lang={lang} />
          <button onClick={() => setShowSettingsModal(true)} title={t.settings} aria-label={t.settings} className="flex items-center space-x-1.5 text-xs font-semibold text-neutral-300 hover:text-white bg-[#18181b] hover:bg-[#27272a] border border-[#27272a] hover:border-[#ffe500]/40 px-3 py-1 rounded-lg transition-all">
            <Settings className="w-3.5 h-3.5 text-[#ffe500]" />
            <span className="hidden sm:inline">{t.settings}</span>
          </button>
          <button onClick={() => { setDeleteError(null); setShowDeleteModal(true); }} title={t.course_delete_btn} aria-label={t.course_delete_btn} className="flex items-center space-x-1.5 text-xs font-semibold text-red-400 hover:text-red-300 bg-red-950/20 hover:bg-red-950/40 border border-red-900/30 px-3 py-1 rounded-lg transition-all">
            <Trash2 className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">{t.course_delete_btn}</span>
          </button>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-4 sm:px-6 pt-8">
        {course.cover_image_url && (
          <div className="w-full h-48 sm:h-64 rounded-3xl overflow-hidden mb-8 border border-[#27272a] shadow-2xl relative bg-black/50">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={course.cover_image_url} alt={`Capa de ${course.subject}`} className="w-full h-full object-cover object-center"
              onError={(e) => { (e.target as HTMLElement).parentElement?.classList.add("hidden"); }} />
            <div className="absolute inset-0 bg-gradient-to-t from-[#0b0b0b] via-transparent to-transparent opacity-90" />
          </div>
        )}

        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-[#ffe500]">
              <EyeOff className="w-4 h-4" /> {en ? "Blind path — one step at a time" : "Caminho cego — um passo por vez"}
            </span>
            <span className="text-xs bg-[#ffe500]/10 text-[#ffe500] border border-[#ffe500]/30 font-black px-2.5 py-0.5 rounded-full">{formatCourseLevel(course.level, lang)}</span>
            {course.category && <span className="text-xs bg-[#18181b] text-neutral-300 border border-[#27272a] font-bold px-2.5 py-0.5 rounded-full uppercase">{course.category}</span>}
          </div>
          <h1 className="text-3xl sm:text-5xl font-black text-white tracking-tight">{course.subject}</h1>
          <p className="text-sm text-neutral-400">
            {en ? "Your next step is revealed only after you prove mastery of the current one — Grammar → Logic → Rhetoric. No map, no counts, no peeking ahead." : "Seu próximo passo só é revelado depois que você prova domínio do atual — Gramática → Lógica → Retórica. Sem mapa, sem contagens, sem espiar o futuro."}
          </p>
        </div>

        {/* CURRENT STEP — the only revealed step. Past steps are below; future stays invisible. */}
        {current ? (
          <motion.div
            key={current.id}
            initial={{ opacity: 0, y: justRevealed ? 20 : 0, scale: justRevealed ? 0.98 : 1 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: justRevealed ? 0.5 : 0.25, ease: "easeOut" }}
            className="mt-8 bg-[#141416] border-2 border-[#ffe500]/60 rounded-3xl p-6 sm:p-8 shadow-2xl shadow-[#ffe500]/5"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center space-x-1.5 text-[10px] font-black uppercase tracking-widest text-[#ffe500]">
                {justRevealed ? <Sparkles className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
                <span>{justRevealed ? (en ? "New step revealed" : "Novo passo revelado") : (en ? "Your current step" : "Seu passo atual")}</span>
              </span>
              <span className="inline-flex items-center space-x-1 text-[10px] font-bold text-neutral-300 bg-[#1f1f23] border border-[#27272a] px-2.5 py-1 rounded-full">
                <Clock className="w-3 h-3 text-[#ffe500]" />
                <span>{en ? "5–10 min episode" : "episódio de 5–10 min"}</span>
              </span>
              <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-300 bg-[#1f1f23] border border-[#27272a] px-2.5 py-1 rounded-full">
                {en ? stageLabel.en : stageLabel.pt}
              </span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-black text-white mt-4 leading-tight">{current.title}</h2>
            <p className="text-sm sm:text-base text-neutral-300 mt-3 leading-relaxed italic border-l-2 border-[#ffe500]/40 pl-4">
              {current.hook}
            </p>
            <p className="text-xs text-neutral-500 mt-4">
              {en
                ? "Prove this step's mastery to unlock the next one. What comes after stays hidden."
                : "Prove o domínio deste passo para desbloquear o próximo. O que vem depois continua oculto."}
            </p>
            <button onClick={() => router.push(`/lesson/${current.id}`)} className="mt-6 w-full sm:w-auto px-8 py-3.5 rounded-2xl bg-[#ffe500] hover:bg-[#fff000] text-black font-black text-sm flex items-center justify-center space-x-2 shadow-lg shadow-[#ffe500]/15 cursor-pointer">
              <Play className="w-4 h-4 fill-current" />
              <span>{en ? "Start this episode" : "Começar este episódio"}</span>
            </button>
          </motion.div>
        ) : certificate ? (
          <div className="mt-8 bg-[#141416] border-2 border-emerald-500/50 rounded-3xl p-6 sm:p-8 text-center">
            <Award className="w-10 h-10 text-emerald-400 mx-auto" />
            <h2 className="text-2xl font-black text-white mt-3">{en ? "Course mastered" : "Curso dominado"}</h2>
            <p className="text-sm text-neutral-400 mt-2">{en ? `Issued ${certificate.issued_at}.` : `Emitido em ${certificate.issued_at}.`}</p>
            <p className="text-xs font-mono text-[#ffe500] mt-3 break-all">{certificate.share_url}</p>
          </div>
        ) : (
          <div className="mt-8 bg-[#141416] border border-[#27272a] rounded-3xl p-6 text-center text-neutral-400 text-sm">
            {en ? "Nothing to do right now — check back soon." : "Nada a fazer agora — volte em breve."}
          </div>
        )}

        {/* COMPLETED STEPS — past only, reviewable */}
        {completed.length > 0 && (
          <div className="mt-8">
            <h3 className="text-xs font-black uppercase tracking-widest text-neutral-400 mb-3">{en ? "Mastered — review anytime" : "Dominado — revise quando quiser"}</h3>
            <div className="space-y-2">
              {completed.map((lesson) => (
                <button key={lesson.id} onClick={() => router.push(`/lesson/${lesson.id}`)} className="w-full flex items-center justify-between p-4 rounded-2xl bg-[#121214] border border-[#27272a] hover:border-emerald-500/40 transition-all text-left cursor-pointer">
                  <span className="flex items-center space-x-3">
                    <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                    <span>
                      <span className="block font-bold text-white text-sm">{lesson.title}</span>
                      <span className="block text-xs text-neutral-500">{lesson.core_concept}</span>
                    </span>
                  </span>
                  <span className="text-xs font-bold text-neutral-400">{en ? "Review" : "Revisar"}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Sources */}
        {course.sources && course.sources.length > 0 && (
          <div className="mt-8 bg-[#141416] border border-[#27272a] rounded-2xl p-5">
            <button onClick={() => setShowSourcesDossier(!showSourcesDossier)} className="w-full flex items-center justify-between text-left group">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 rounded-xl bg-[#ffe500]/10 border border-[#ffe500]/30 flex items-center justify-center text-[#ffe500]"><ShieldCheck className="w-4 h-4" /></div>
                <span className="text-xs font-black uppercase tracking-wider text-[#ffe500]">{t.course_sources_badge}</span>
              </div>
              {showSourcesDossier ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
            </button>
            {showSourcesDossier && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-4">
                {course.sources.map((src, idx) => src.url ? (
                  <a key={idx} href={src.url} target="_blank" rel="noopener noreferrer" className="flex items-center justify-between p-3 rounded-xl bg-[#1a1a1e] hover:bg-[#222228] border border-[#27272a] transition-all">
                    <span className="truncate pr-2"><span className="text-xs font-bold text-white block truncate">{src.title}</span><span className="text-[10px] text-neutral-500 font-mono">{src.domain}</span></span>
                  </a>
                ) : (
                  <div key={idx} title={src.description} className={`flex items-center justify-between p-3 rounded-xl border transition-all ${src.citation ? "bg-[#1a1a1e] border-[#ffe500]/25" : "bg-[#1a1a1e] border-[#27272a]"}`}>
                    <span className="truncate pr-2"><span className="text-xs font-bold text-white block truncate">{src.title}</span><span className="text-[10px] text-neutral-500 font-mono">{src.domain}</span></span>
                    {src.citation && <span className="shrink-0 text-[9px] font-black uppercase tracking-wider text-[#ffe500]">{en ? "Citation" : "Citação"}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {showDeleteModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#141416] border border-[#27272a] rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-2xl relative">
            <button onClick={() => !isDeleting && setShowDeleteModal(false)} disabled={isDeleting} className="absolute top-5 right-5 text-neutral-400 hover:text-white p-1 rounded-lg hover:bg-neutral-800/50 cursor-pointer"><X className="w-5 h-5" /></button>
            <div className="flex items-start space-x-4">
              <div className="w-12 h-12 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center shrink-0 text-red-400"><AlertTriangle className="w-6 h-6" /></div>
              <div>
                <h3 className="text-lg sm:text-xl font-black text-white">{t.course_delete_confirm_title}</h3>
                <p className="text-sm text-neutral-300 mt-2"><strong className="text-white">&ldquo;{course.subject}&rdquo;</strong></p>
              </div>
            </div>
            {deleteError && <div className="mt-4 p-3 rounded-xl bg-red-950/30 border border-red-800/40 text-red-400 text-xs font-semibold">{deleteError}</div>}
            <div className="mt-6 flex flex-col-reverse sm:flex-row items-center justify-end gap-3">
              <button type="button" onClick={() => setShowDeleteModal(false)} disabled={isDeleting} className="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-[#27272a] hover:bg-[#1f1f23] text-neutral-300 font-bold text-xs cursor-pointer">{t.course_delete_cancel}</button>
              <button type="button" onClick={handleDeleteCourse} disabled={isDeleting} className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-red-600 hover:bg-red-700 text-white font-bold text-xs cursor-pointer disabled:opacity-50">{isDeleting ? (en ? "Deleting..." : "Excluindo...") : t.course_delete_proceed}</button>
            </div>
          </div>
        </div>
      )}

      <SettingsModal isOpen={showSettingsModal} onClose={() => setShowSettingsModal(false)} lang={lang} />
    </main>
  );
}
