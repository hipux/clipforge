interface ProgressBarProps {
  progress: number // 0-100
  message?: string
  className?: string
  showPercent?: boolean
  tone?: 'cyan' | 'accent' | 'warm' | 'success'
}

export default function ProgressBar({
  progress,
  message,
  className = '',
  showPercent = true,
  tone = 'cyan',
}: ProgressBarProps) {
  const pct = Math.min(100, Math.max(0, progress))

  // Pick the gradient stops based on the chosen tone.
  //   • cyan    : default — classic "download" feel (kept for back-compat)
  //   • accent  : indigo, matches the dashboard's primary tint
  //   • warm    : amber, used for "paused" or staging states
  //   • success : emerald (also used when pct === 100 regardless of tone)
  const gradient =
    pct === 100
      ? 'linear-gradient(90deg, #10b981, #34d399)'
      : tone === 'accent'
        ? 'linear-gradient(90deg, #6366f1, #818cf8)'
        : tone === 'warm'
          ? 'linear-gradient(90deg, #f59e0b, #fbbf24)'
          : tone === 'success'
            ? 'linear-gradient(90deg, #10b981, #34d399)'
            : 'linear-gradient(90deg, #06b6d4, #38bdf8)'

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
          style={{ width: `${pct}%`, background: gradient }}
        />
      </div>
    </div>
  )
}
