import { Captions } from 'lucide-react'
import { useAppStore } from '../store/useAppStore'

const styles = [
  {
    id: 'karaoke',
    name: 'Karaoke',
    description: '1-2 words, yellow highlight, TikTok style',
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
    id: 'bold',
    name: 'Bold White',
    description: '2-3 words, large white, thick outline',
    preview: (
      <div className="bg-gradient-to-b from-slate-800 to-slate-900 rounded-lg p-4 h-24 flex items-end justify-center">
        <span className="text-white font-bold text-xl" style={{ textShadow: '3px 3px 0 #000, -3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000' }}>
          SAMPLE TEXT
        </span>
      </div>
    ),
  },
  {
    id: 'neon',
    name: 'Neon',
    description: '1-2 words, cyan glow, dark box',
    preview: (
      <div className="bg-gradient-to-b from-slate-800 to-slate-900 rounded-lg p-4 h-24 flex items-end justify-center">
        <span className="text-cyan-400 font-bold text-lg px-3 py-1.5 bg-black/70 rounded" style={{ textShadow: '0 0 10px #06b6d4, 0 0 20px #06b6d4' }}>
          SAMPLE TEXT
        </span>
      </div>
    ),
  },
  {
    id: 'minimal',
    name: 'Minimal',
    description: '3-4 words, small clean white, subtle',
    preview: (
      <div className="bg-gradient-to-b from-slate-800 to-slate-900 rounded-lg p-4 h-24 flex items-end justify-center">
        <span className="text-white text-sm" style={{ textShadow: '1px 1px 2px rgba(0,0,0,0.4)' }}>
          sample text here
        </span>
      </div>
    ),
  },
  {
    id: 'cinematic',
    name: 'Cinematic',
    description: '2-3 words, letter-spacing, black bar',
    preview: (
      <div className="bg-gradient-to-b from-slate-800 to-slate-900 rounded-lg p-4 h-24 flex items-end justify-center">
        <span className="text-white text-lg font-medium px-6 py-2 bg-black/60" style={{ letterSpacing: '0.1em' }}>
          SAMPLE TEXT
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
