import { Check, Clock, TrendingUp, Film, Play } from 'lucide-react'
import { MomentCandidate } from '../store/useAppStore'

interface MomentCardProps {
  moment: MomentCandidate
  isSelected: boolean
  onToggle: () => void
  onPreview?: () => void
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

function scoreColor(pct: number) {
  if (pct >= 75) return 'text-green-700 bg-green-50 border-green-200'
  if (pct >= 50) return 'text-amber-700 bg-amber-50 border-amber-200'
  return 'text-slate-600 bg-slate-50 border-slate-200'
}

export default function MomentCard({ moment, isSelected, onToggle, onPreview }: MomentCardProps) {
  const duration = moment.end - moment.start
  const pct = moment.score <= 1 ? Math.round(moment.score * 100) : Math.round(moment.score)

  return (
    <div
      onClick={onToggle}
      className={`group relative flex gap-4 p-3 cursor-pointer select-none rounded-2xl bg-white transition-all duration-200
        ${isSelected
          ? 'ring-2 ring-accent border border-transparent shadow-card-hover'
          : 'border border-slate-200 hover:border-slate-300 hover:shadow-card-hover hover:-translate-y-0.5'
        }`}
    >
      {/* Vertical 9:16 preview */}
      <div className="relative w-[120px] sm:w-[132px] shrink-0 aspect-[9/16] rounded-xl overflow-hidden bg-slate-900">
        {moment.thumbnail_url ? (
          <img src={moment.thumbnail_url} alt="Clip preview" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Film size={24} className="text-slate-600" />
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/55 via-transparent to-black/15" />

        {/* Preview (play) button */}
        {onPreview && (
          <button
            onClick={(e) => { e.stopPropagation(); onPreview() }}
            className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
            aria-label="Preview moment"
          >
            <span className="w-11 h-11 rounded-full bg-white/90 backdrop-blur flex items-center justify-center shadow-lg hover:scale-105 transition-transform">
              <Play size={20} className="text-slate-900 ml-0.5" fill="currentColor" />
            </span>
          </button>
        )}

        {/* Select check */}
        <div className={`absolute top-2 left-2 w-6 h-6 rounded-full flex items-center justify-center border transition-all duration-150
          ${isSelected
            ? 'bg-accent border-accent text-white'
            : 'bg-white/85 backdrop-blur border-white/70 text-transparent group-hover:border-accent group-hover:text-accent/40'
          }`}>
          <Check size={14} strokeWidth={3} />
        </div>

        {/* Time at bottom */}
        <div className="absolute bottom-2 left-2 right-2 flex items-center gap-1 text-white text-[11px] font-medium">
          <Clock size={11} />
          <span className="truncate">{formatTime(moment.start)}–{formatTime(moment.end)}</span>
        </div>
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0 flex flex-col py-0.5">
        <div className="flex items-center justify-between gap-2">
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border ${scoreColor(pct)}`}>
            <TrendingUp size={10} />
            {pct}% match
          </span>
          <span className="text-xs text-slate-400 shrink-0">{Math.round(duration)}s</span>
        </div>

        <p className="text-sm text-slate-600 leading-snug mt-2 line-clamp-4 flex-1">{moment.reason}</p>

        <div className={`mt-2 text-xs font-semibold transition-colors ${isSelected ? 'text-accent' : 'text-slate-400 group-hover:text-slate-600'}`}>
          {isSelected ? '✓ Selected for export' : 'Tap to select'}
        </div>
      </div>
    </div>
  )
}
