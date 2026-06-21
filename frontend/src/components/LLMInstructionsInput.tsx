interface Props {
  value: string
  onChange: (v: string) => void
  isGPU: boolean
}

export function LLMInstructionsInput({ value, onChange, isGPU }: Props) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-zinc-300 flex items-center gap-2">
        <span>🧠 Инструкции для ИИ</span>
        {!isGPU && (
          <span className="text-xs text-yellow-500 bg-yellow-500/10 px-2 py-0.5 rounded">
            GPU недоступен — ИИ-анализ отключен
          </span>
        )}
      </label>
      <textarea
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={!isGPU}
        placeholder={isGPU
          ? 'Например: выбирай только смешные моменты, избегай технических объяснений...'
          : 'Требуется GPU для ИИ-анализа'
        }
        className="w-full h-24 px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm text-zinc-200 placeholder-zinc-500 resize-none focus:outline-none focus:border-purple-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        maxLength={500}
      />
      <div className="text-xs text-zinc-500 text-right">
        {value.length}/500
      </div>
    </div>
  )
}
