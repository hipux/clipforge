import { Captions } from 'lucide-react'
import { useAppStore } from '../store/useAppStore'

const styles = [
  {
    id: 'karaoke',
    name: 'Karaoke',
    description: '1-2 words, yellow highlight, TikTok style',
    renderSubtitle: (
      <span className="font-bold text-lg">
        <span className="text-yellow-400" style={{ textShadow: '1px 1px 3px rgba(0,0,0,0.6)' }}>SAMPLE</span>
        <span className="text-white ml-1" style={{ textShadow: '1px 1px 3px rgba(0,0,0,0.6)' }}>TEXT</span>
      </span>
    ),
  },
  {
    id: 'bold',
    name: 'Bold White',
    description: '2-3 words, large white, thick outline',
    renderSubtitle: (
      <span className="text-white font-bold text-xl" style={{ textShadow: '3px 3px 0 #000, -3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000' }}>
        SAMPLE TEXT
      </span>
    ),
  },
  {
    id: 'neon',
    name: 'Neon',
    description: '1-2 words, cyan glow, dark box',
    renderSubtitle: (
      <span className="text-cyan-400 font-bold text-lg px-3 py-1.5 bg-black/70 rounded" style={{ textShadow: '0 0 10px #06b6d4, 0 0 20px #06b6d4' }}>
        SAMPLE TEXT
      </span>
    ),
  },
  {
    id: 'minimal',
    name: 'Minimal',
    description: '3-4 words, small clean white, subtle',
    renderSubtitle: (
      <span className="text-white text-sm">sample text here</span>
    ),
  },
  {
    id: 'cinematic',
    name: 'Cinematic',
    description: '2-3 words, letter-spacing, black bar',
    renderSubtitle: (
      <span className="text-white text-lg font-medium px-6 py-2 bg-black/60" style={{ letterSpacing: '0.1em' }}>
        SAMPLE TEXT
      </span>
    ),
  },
]

export default function SubtitleStylePicker() {
  const { globalEffects, updateGlobalEffect, currentVideo, moments } = useAppStore()
  const selectedStyle = globalEffects.subtitle_style || 'karaoke'

  const handleStyleChange = (styleId: string) => {
    updateGlobalEffect({ subtitle_style: styleId })
  }

  // Use the first moment's thumbnail (9:16 with blurred background) or fallback to video thumbnail
  const previewBg = moments.length > 0 ? moments[0].thumbnail_url : currentVideo?.thumbnail_url

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Captions size={16} className="text-accent" />
        <span className="font-semibold text-slate-200 text-sm">Subtitle Style</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {styles.map((style) => (
          <button
            key={style.id}
            onClick={() => handleStyleChange(style.id)}
            className={`text-left rounded-xl border transition-all ${
              selectedStyle === style.id
                ? 'bg-accent/10 border-accent/40 ring-2 ring-accent/20'
                : 'bg-surface-2 border-slate-700 hover:border-slate-600 hover:bg-white/[0.03]'
            }`}
          >
            {/* Video frame preview - 9:16 vertical format */}
            <div className="relative w-full aspect-[9/16] rounded-t-lg overflow-hidden">
              {/* Background: moment thumbnail (9:16 with blur) if available, else video thumbnail or gradient */}
              {previewBg ? (
                <img 
                  src={previewBg} 
                  alt="Video frame" 
                  className="absolute inset-0 w-full h-full object-cover" 
                />
              ) : (
                <div className="absolute inset-0 bg-gradient-to-b from-[#1a1a2e] via-[#16213e] to-[#0f3460]">
                  {/* Subtle person silhouette */}
                  <svg viewBox="0 0 200 200" className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-4/5 w-auto opacity-10">
                    <ellipse cx="100" cy="60" rx="40" ry="40" fill="#94a3b8"/>
                    <path d="M30 200 Q100 120 170 200" fill="#94a3b8"/>
                  </svg>
                </div>
              )}
              
              {/* Subtitle overlay at bottom */}
              <div className="absolute bottom-3 left-0 right-0 flex justify-center">
                {style.renderSubtitle}
              </div>
            </div>

            {/* Info */}
            <div className="px-3 pb-3 pt-2">
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
