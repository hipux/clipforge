import { CheckCircle2, Clock, TrendingUp, Film } from 'lucide-react'
import { MomentCandidate } from '../store/useAppStore'

interface MomentCardProps {
  moment: MomentCandidate
  isSelected: boolean
  onToggle: () => void
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

function scoreColor(score: number) {
  if (score >= 75) return 'text-success bg-success/10 border-success/20'
  if (score >= 50) return 'text-warning bg-warning/10 border-warning/20'
  return 'text-slate-400 bg-slate-800 border-slate-700'
}

export default function MomentCard({ moment, isSelected, onToggle }: MomentCardProps) {
  const duration = moment.end - moment.start

  return (
    <div
      className={`
        flex gap-4 p-4 rounded-xl border cursor-pointer
        transition-all duration-200 select-none
        ${isSelected
          ? 'bg-accent/6 border-accent/30 shadow-glow'
          : 'bg-surface border-slate-800 hover:border-slate-700 hover:bg-white/[0.02]'
        }
      `}
      onClick={onToggle}
    >
      {/* Thumbnail */}
      {moment.thumbnail_url ? (
        <img
          src={moment.thumbnail_url}
          alt="Moment thumbnail"
          className="w-28 h-[63px] object-cover rounded-lg shrink-0 border border-slate-700"
        />
      ) : (
        <div className="w-28 h-[63px] bg-surface-2 rounded-lg shrink-0 border border-slate-700/50 flex items-center justify-center">
          <Film size={22} className="text-slate-600" />
        </div>
      )}

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          {/* Time range */}
          <div>
            <div className="font-semibold text-sm text-slate-100 flex items-center gap-1.5">
              <Clock size={13} className="text-slate-500" />
              {formatTime(moment.start)} – {formatTime(moment.end)}
            </div>
            <div className="text-xs text-slate-500 mt-0.5">{Math.round(duration)}s clip</div>
          </div>

          {/* Score + check */}
          <div className="flex flex-col items-end gap-1.5 shrink-0">
            <span className={`badge border text-xs font-semibold ${scoreColor(moment.score)}`}>
              <TrendingUp size={10} />
              {Math.round(moment.score)}%
            </span>
            {isSelected && (
              <CheckCircle2 size={16} className="text-accent" />
            )}
          </div>
        </div>

        {/* Reason tag */}
        <div className="mt-2">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-surface-2 border border-slate-700/50 rounded text-[11px] text-slate-400">
            {moment.reason}
          </span>
        </div>
      </div>
    </div>
  )
}
