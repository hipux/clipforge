import { ReactNode } from 'react'
import { Check } from 'lucide-react'

interface EffectToggleProps {
  icon: ReactNode
  label: string
  description: string
  enabled: boolean
  onToggle: () => void
}

export default function EffectToggle({
  icon,
  label,
  description,
  enabled,
  onToggle,
}: EffectToggleProps) {
  return (
    <div
      className={`
        flex items-center gap-4 p-4 rounded-xl border cursor-pointer
        transition-all duration-200 select-none
        ${enabled
          ? 'bg-accent/8 border-accent/30 shadow-glow'
          : 'bg-surface-2 border-slate-200/50 hover:border-slate-300 hover:bg-slate-50'
        }
      `}
      onClick={onToggle}
    >
      {/* Icon */}
      <div
        className={`
          w-10 h-10 rounded-lg flex items-center justify-center shrink-0 transition-colors
          ${enabled ? 'bg-accent/20 text-accent' : 'bg-white text-slate-500'}
        `}
      >
        {icon}
      </div>

      {/* Text */}
      <div className="flex-1 min-w-0">
        <div className={`font-medium text-sm ${enabled ? 'text-slate-900' : 'text-slate-700'}`}>
          {label}
        </div>
        <div className="text-xs text-slate-500 mt-0.5 leading-snug">{description}</div>
      </div>

      {/* Toggle */}
      <div
        className={`
          relative w-11 h-6 rounded-full transition-colors duration-200 shrink-0
          ${enabled ? 'bg-accent' : 'bg-slate-100'}
        `}
      >
        <div
          className={`
            absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-200
            ${enabled ? 'translate-x-5' : 'translate-x-0.5'}
          `}
        >
          {enabled && (
            <Check size={11} className="text-accent absolute inset-0 m-auto" />
          )}
        </div>
      </div>
    </div>
  )
}
