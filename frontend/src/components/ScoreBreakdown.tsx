import { Sparkles, MessageSquare, Zap, Users as UsersIcon, Info } from 'lucide-react'
import type { ScoreBreakdown as T } from '../store/useAppStore'

interface Props {
  score: T | null | undefined
}

function barColor(v: number) {
  if (v >= 0.7) return 'bg-emerald-500'
  if (v >= 0.45) return 'bg-amber-400'
  return 'bg-rose-400'
}

function overallClass(v: number) {
  if (v >= 85) return 'text-emerald-600 bg-emerald-50 border-emerald-200'
  if (v >= 70) return 'text-amber-700 bg-amber-50 border-amber-200'
  return 'text-slate-700 bg-slate-50 border-slate-200'
}

function Bar({ label, value, Icon }: { label: string; value: number; Icon: typeof Sparkles }) {
  return (
    <div className="flex items-center gap-2 text-xs text-slate-600">
      <Icon size={12} className="text-slate-400 shrink-0" />
      <span className="w-20 shrink-0 text-[11px] uppercase tracking-wider text-slate-500 font-semibold">{label}</span>
      <div className="flex-1 h-1.5 bg-slate-200 rounded-full overflow-hidden">
        <div
          className={`h-full ${barColor(value)} transition-all duration-300`}
          style={{ width: `${Math.max(0, Math.min(100, value * 100))}%` }}
        />
      </div>
      <span className="w-9 text-right text-[11px] tabular-nums text-slate-500">{value.toFixed(2)}</span>
    </div>
  )
}

export default function ScoreBreakdown({ score }: Props) {
  if (!score) {
    return (
      <div className="flex items-center gap-1.5 text-[11px] text-slate-400 px-2 py-1 rounded-md bg-slate-50 border border-dashed border-slate-200">
        <Info size={11} />
        <span>no AI score (re-process to generate)</span>
      </div>
    )
  }
  return (
    <div className="rounded-xl border border-slate-200 bg-white/60 p-3 space-y-2.5">
      {/* Top row: overall + content badge */}
      <div className="flex items-center justify-between gap-2">
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border ${overallClass(score.overall)}`}>
          <Sparkles size={11} />
          {score.overall}% match
        </span>
        {score.content_type && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
            <span aria-hidden>{score.content_emoji || '🎬'}</span>
            {score.content_type}
          </span>
        )}
      </div>

      {/* 3 mini bars */}
      <div className="space-y-1.5">
        <Bar label="Hook"   value={score.hook}           Icon={MessageSquare} />
        <Bar label="Clear"  value={score.self_contained} Icon={Sparkles} />
        <Bar label="Pacing" value={score.pacing}         Icon={Zap} />
      </div>

      {/* Speakers (from cross-modal — only if any) */}
      {score.speakers.length > 0 && (
        <div className="flex items-center gap-1.5 text-[11px] text-slate-600 pt-1 border-t border-slate-100">
          <UsersIcon size={11} className="text-slate-400 shrink-0" />
          <span className="font-medium">Speakers:</span>
          <div className="flex flex-wrap gap-1">
            {score.speakers.map((s) => (
              <span key={s} className="px-1.5 py-0.5 rounded-md bg-slate-100 border border-slate-200 text-slate-700">
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Reason — short LLM verdict */}
      {score.reason && (
        <p className="text-[12px] leading-snug text-slate-600 italic border-t border-slate-100 pt-1.5 line-clamp-3">
          “{score.reason}”
        </p>
      )}
    </div>
  )
}
