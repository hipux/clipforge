import { Captions } from 'lucide-react'
import { useAppStore } from '../store/useAppStore'

const styles = [
  {
    id: 'karaoke',
    name: 'Karaoke',
    description: 'Word-by-word yellow highlight, TikTok favorite',
    renderSubtitle: (
      <span className="font-extrabold text-[11px] leading-tight tracking-tight" style={{ textShadow: '0 2px 4px rgba(0,0,0,0.7)' }}>
        <span className="text-white">THIS</span>{' '}
        <span className="text-yellow-300" style={{ textShadow: '0 0 6px rgba(250,204,21,0.7), 0 2px 4px rgba(0,0,0,0.8)' }}>CHANGES</span>{' '}
        <span className="text-white">IT</span>
      </span>
    ),
  },
  {
    id: 'neon',
    name: 'Neon',
    description: 'Glowing cyan letters, electric look',
    renderSubtitle: (
      <span className="font-extrabold text-[11px] tracking-wide text-cyan-300" style={{ textShadow: '0 0 6px #22d3ee, 0 0 12px #06b6d4, 0 0 20px #0891b2' }}>
        LET'S GO
      </span>
    ),
  },
  {
    id: 'hormozi',
    name: 'Hormozi',
    description: 'Bold caps, black stroke, green keyword pop',
    renderSubtitle: (
      <span className="font-black text-[11px] leading-tight tracking-tight uppercase" style={{ WebkitTextStroke: '2px #000', paintOrder: 'stroke fill' }}>
        <span className="text-white">YOU</span>{' '}
        <span className="text-[#22c55e]">NEED</span>{' '}
        <span className="text-white">THIS</span>
      </span>
    ),
  },
  {
    id: 'highlight',
    name: 'Highlight',
    description: 'Marker-style background, clean & bold',
    renderSubtitle: (
      <span className="font-extrabold text-[10px] uppercase leading-relaxed" style={{ boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone' }}>
        <span className="bg-yellow-300 text-black px-1 py-0.5 rounded-sm">READ THIS NOW</span>
      </span>
    ),
  },
]

export default function SubtitleStylePicker() {
  const { globalEffects, updateGlobalEffects, currentVideo, moments } = useAppStore()
  const selectedStyle = globalEffects.subtitle_style || 'karaoke'

  const handleStyleChange = (styleId: string) => {
    updateGlobalEffects({ subtitle_style: styleId })
  }

  const previewBg = moments.length > 0 ? moments[0].thumbnail_url : currentVideo?.thumbnail_url

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Captions size={16} className="text-accent" />
        <span className="font-semibold text-slate-800 text-sm">Subtitle Style</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {styles.map((style) => (
          <button
            key={style.id}
            onClick={() => handleStyleChange(style.id)}
            className={`text-left rounded-xl border transition-all ${
              selectedStyle === style.id
                ? 'bg-accent/10 border-accent/40 ring-2 ring-accent/20'
                : 'bg-surface-2 border-slate-200 hover:border-slate-300 hover:bg-slate-50'
            }`}
          >
            <div className="relative w-full aspect-[9/16] rounded-t-lg overflow-hidden">
              {previewBg ? (
                <img
                  src={previewBg}
                  alt="Video frame"
                  className="absolute inset-0 w-full h-full object-cover"
                />
              ) : (
                <div className="absolute inset-0 bg-gradient-to-b from-[#1a1a2e] via-[#16213e] to-[#0f3460]">
                  <svg viewBox="0 0 200 200" className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-4/5 w-auto opacity-10">
                    <ellipse cx="100" cy="60" rx="40" ry="40" fill="#94a3b8"/>
                    <path d="M30 200 Q100 120 170 200" fill="#94a3b8"/>
                  </svg>
                </div>
              )}

              <div className="absolute bottom-3 left-0 right-0 flex justify-center px-1">
                {style.renderSubtitle}
              </div>
            </div>

            <div className="px-2 pb-2 pt-1.5">
              <div className={`font-medium text-sm mb-0.5 ${selectedStyle === style.id ? 'text-accent' : 'text-slate-800'}`}>
                {style.name}
              </div>
              <div className="text-[10px] leading-snug text-slate-500">{style.description}</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}