interface ProgressBarProps {
  progress: number // 0-100
  message?: string
  className?: string
  showPercent?: boolean
}

export default function ProgressBar({
  progress,
  message,
  className = '',
  showPercent = true,
}: ProgressBarProps) {
  const pct = Math.min(100, Math.max(0, progress))

  return (
    <div className={className}>
      {(message || showPercent) && (
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm text-slate-500 truncate">{message || 'Processing...'}</span>
          {showPercent && (
            <span className="text-sm font-semibold text-accent ml-2 tabular-nums shrink-0">
              {Math.round(pct)}%
            </span>
          )}
        </div>
      )}
      <div className="w-full bg-white rounded-full h-2 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-300 ease-out"
          style={{
            width: `${pct}%`,
            background: pct === 100
              ? 'linear-gradient(90deg, #10b981, #34d399)'
              : 'linear-gradient(90deg, #06b6d4, #38bdf8)',
          }}
        />
      </div>
    </div>
  )
}
