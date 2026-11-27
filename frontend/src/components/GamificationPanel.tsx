"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Flame, Sparkles, Trophy, Zap } from "lucide-react";
import { AUTH_CHANGED_EVENT, getProfileStats, ProfileStats } from "@/lib/api";

/**
 * Retention layer: XP, streak, level ring and badges.
 * Everything shown here is derived from COMPLETED work only — the API never
 * returns totals for future lessons (Fog-of-War contract).
 */
export const PROFILE_UPDATED_EVENT = "trivium:profile-updated";

export function notifyProfileUpdated() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(PROFILE_UPDATED_EVENT));
  }
}

const BADGE_META: Record<string, { icon: string; en: string; pt: string }> = {
  "first-step": { icon: "🌱", en: "First Step", pt: "Primeiro Passo" },
  "scholar": { icon: "📚", en: "Scholar", pt: "Estudioso" },
  "master": { icon: "🏆", en: "Master", pt: "Mestre" },
  "on-fire": { icon: "🔥", en: "On Fire", pt: "Em Chamas" },
  "unstoppable": { icon: "⚡", en: "Unstoppable", pt: "Imparável" },
};

interface Props {
  lang?: "pt-BR" | "en-US";
  compact?: boolean;
  className?: string;
}

export default function GamificationPanel({ lang = "pt-BR", compact = false, className = "" }: Props) {
  const [stats, setStats] = useState<ProfileStats | null>(null);
  const en = lang === "en-US";

  const refresh = useCallback(() => {
    getProfileStats().then(setStats).catch(() => { /* gamification is best-effort */ });
  }, []);

  useEffect(() => {
    refresh();
    window.addEventListener(PROFILE_UPDATED_EVENT, refresh);
    window.addEventListener(AUTH_CHANGED_EVENT, refresh);
    window.addEventListener("focus", refresh);
    return () => {
      window.removeEventListener(PROFILE_UPDATED_EVENT, refresh);
      window.removeEventListener(AUTH_CHANGED_EVENT, refresh);
      window.removeEventListener("focus", refresh);
    };
  }, [refresh]);

  if (!stats) return null;

  const xp = stats.xp || 0;
  const level = stats.level || 1;
  // level_for_xp = 1 + floor(sqrt(xp/50)); ring fills across the current band.
  const bandStart = 50 * Math.pow(level - 1, 2);
  const bandEnd = 50 * Math.pow(level, 2);
  const ringPct = level >= 12 ? 100 : Math.max(0, Math.min(100, ((xp - bandStart) / Math.max(1, bandEnd - bandStart)) * 100));
  const radius = compact ? 17 : 26;
  const circumference = 2 * Math.PI * radius;
  const earnedBadges = stats.badges || [];

  return (
    <div
      className={`flex items-center gap-3 bg-[#141416] border border-[#27272a] rounded-xl ${compact ? "px-2.5 py-1.5" : "px-4 py-3"} ${className}`}
      data-testid="gamification-panel"
      title={en ? "Progress is earned only from completed steps" : "O progresso vem apenas de passos concluídos"}
    >
      {/* Level ring */}
      <div className="relative shrink-0" style={{ width: radius * 2 + 6, height: radius * 2 + 6 }}>
        <svg viewBox={`0 0 ${radius * 2 + 6} ${radius * 2 + 6}`} className="w-full h-full -rotate-90">
          <circle cx={radius + 3} cy={radius + 3} r={radius} fill="none" stroke="#27272a" strokeWidth="4" />
          <circle
            cx={radius + 3} cy={radius + 3} r={radius} fill="none" stroke="#ffe500" strokeWidth="4"
            strokeLinecap="round" strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - ringPct / 100)}
            style={{ transition: "stroke-dashoffset 600ms ease" }}
          />
        </svg>
        <span className={`absolute inset-0 flex items-center justify-center font-black text-[#ffe500] ${compact ? "text-[10px]" : "text-sm"}`}>
          {level}
        </span>
      </div>

      <div className="flex flex-col min-w-0">
        <div className="flex items-center gap-2.5 text-[11px] font-black tracking-wide">
          <span className="text-[#ffe500] flex items-center gap-1"><Zap className={compact ? "w-3 h-3" : "w-3.5 h-3.5"} fill="currentColor" />{xp} XP</span>
          <span className="text-orange-400 flex items-center gap-1"><Flame className={compact ? "w-3 h-3" : "w-3.5 h-3.5"} />{stats.streak_days || 0}</span>
          {!compact && <span className="text-neutral-400 flex items-center gap-1"><Trophy className="w-3.5 h-3.5" />{stats.completed_lessons || 0}</span>}
        </div>
        {!compact && (
          <div className="flex items-center gap-1 mt-1.5 flex-wrap">
            {earnedBadges.length === 0 ? (
              <span className="text-[10px] text-neutral-500">{en ? "Badges unlock as you learn" : "Conquistas desbloqueiam com a prática"}</span>
            ) : earnedBadges.map((b) => {
              const meta = BADGE_META[b] || { icon: "🎖️", en: b, pt: b };
              return (
                <span key={b} title={en ? meta.en : meta.pt}
                  className="inline-flex items-center gap-1 rounded-full bg-[#1f1f23] border border-[#3f3f46] px-1.5 py-0.5 text-[9px] font-bold text-neutral-300">
                  {meta.icon} <span className="hidden sm:inline">{en ? meta.en : meta.pt}</span>
                </span>
              );
            })}
          </div>
        )}
      </div>
      {compact && earnedBadges.length > 0 && (
        <span className="text-[10px] text-neutral-500 hidden md:inline" title={earnedBadges.join(", ")}>
          <Sparkles className="w-3 h-3 inline text-[#ffe500]" /> {earnedBadges.length}
        </span>
      )}
    </div>
  );
}
