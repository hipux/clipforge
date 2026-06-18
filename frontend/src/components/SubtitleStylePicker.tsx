import { Captions } from 'lucide-react'
import { useAppStore } from '../store/useAppStore'

const styles = [
  {
    id: 'classic',
    name: 'Classic',
    description: 'White text, black outline, clean',
    preview: (
      <div className="bg-gradient-to-b from-slate-800 to-slate-900 rounded-lg p-4 h-24 flex items-end justify-center">
        <span className="text-white font-medium text-lg" style={{ textShadow: '2px 2px 4px rgba(0,0,0,0.8)' }}>
          SAMPLE TEXT
        </span>
      </div>
    ),
  },
  {
    id: 'karaoke',
    name: 'Karaoke',
    description: 'Yellow highlight, TikTok style',
    preview: (
      <div className="bg-gradient-to-b from-slate-800 to-slate-900 rounded-lg p-4 h-24 flex items-end justify-center">
        <span className="font-bold text-lg">
          <span className="text-yellow-400" style={{ textShadow: '1px 1px 3px rgba(0,0,0,0.6)' }}>SAMPLE</span>
          <span className="text-white ml-1" style={{ textShadow: '1px 1px 3px rgba(0,0,0,0.6)' }}>TEXT</span>
        </span>
      </div>
    ),
  },
  {
    id: 'box',
    name: 'Box',
    description: 'Dark background, modern',
    preview: (
      <div className="bg-gradient-to-b from-slate-800 to-slate-900 rounded-lg p-4 h-24 flex items-end justify-center">
        <span className="text-white text-lg px-4 py-1.5 bg-black/60 rounded">
          SAMPLE TEXT
        </span>
      </div>
    ),
  },
  {
    id: 'outlined',
    name: 'Outlined',
    description: 'Thick cyan outline, bold',
    preview: (
      <div className="bg-gradient-to-b from-slate-800 to-slate-900 rounded-lg p-4 h-24 flex items-end justify-center">
        <span
          className="text-white font-bold text-xl"
          style={{
            textShadow: '0 0 8px #06b6d4, 0 0 12px #06b6d4, 2px 2px 0 #06b6d4, -2px -2px 0 #06b6d4, 2px -2px 0 #06b6d4, -2px 2px 0 #06b6d4',
          }}
        >
          SAMPLE TEXT
        </span>
      </div>
    ),
  },
  {
    id: 'minimal',
    name: 'Minimal',
    description: 'Subtle, clean aesthetic',
    preview: (
      <div className="bg-gradient-to-b from-slate-800 to-slate-900 rounded-lg p-4 h-24 flex items-end justify-center">
        <span className="text-slate-400 text-sm">
          sample text
        </span>
      </div>
    ),
  },
]

export default function SubtitleStylePicker() {
  const { globalEffects, updateGlobalEffects } = useAppStore()
  const selectedStyle = globalEffects.subtitle_style || 'karaoke'

  const handleStyleSelect = (styleId: string) => {
    updateGlobalEffects({ subtitle_style: styleId })
  }

  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-4">
        <Captions size={16} className="text-accent" />
        <h2 className="font-semibold text-slate-200">Subtitle Style</h2>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {styles.map((style) => (
          <button
            key={style.id}
            onClick={() => handleStyleSelect(style.id)}
            className={`text-left rounded-xl border transition-all ${
              selectedStyle === style.id
                ? 'bg-accent/10 border-accent/40 ring-2 ring-accent/20'
                : 'bg-surface-2 border-slate-700 hover:border-slate-600 hover:bg-white/[0.03]'
            }`}
          >
            {/* Preview */}
            <div className="mb-3">{style.preview}</div>

            {/* Info */}
            <div className="px-3 pb-3">
              <div className={`font-medium text-sm mb-0.5 ${selectedStyle === style.id ? 'text-accent' : 'text-slate-200'}`}>
                {style.name}
              </div>
              <div className="text-xs text-slate-500">{style.description}</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
