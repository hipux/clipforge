import { Captions, Check } from 'lucide-react'
import { useAppStore } from '../store/useAppStore'

type Style = {
  id: string
  name: string
  description: string
  renderSubtitle: JSX.Element
}

// NOTE: these previews are designed to visually match the ASS styles produced
// by the backend subtitle renderer (see services/subtitles). Keep them in sync.
const styles: Style[] = [
  {
    id: 'karaoke',
    name: 'Karaoke',
    description: 'Word-by-word yellow highlight',
    renderSubtitle: (
      <span className="font-extrabold leading-tight tracking-tight text-[13px]" style={{ textShadow: '0 2px 5px rgba(0,0,0,0.85)' }}>
        <span className="text-white">THIS</span>{' '}
        <span className="text-yellow-300" style={{ textShadow: '0 0 10px rgba(250,204,21,0.85), 0 2px 4px rgba(0,0,0,0.9)' }}>CHANGES</span>{' '}
        <span className="text-white">IT</span>
      </span>
    ),
  },
  {
    id: 'neon',
    name: 'Neon',
    description: 'Glowing cyan, electric look',
    renderSubtitle: (
      <span className="font-extrabold tracking-wide text-cyan-300 text-[13px]" style={{ textShadow: '0 0 8px #22d3ee, 0 0 16px #06b6d4, 0 0 28px #0891b2' }}>
        LET'S GO
      </span>
    ),
  },
  {
    id: 'hormozi',
    name: 'Hormozi',
    description: 'Bold caps, green keyword pop',
    renderSubtitle: (
      <span className="font-black leading-tight tracking-tight uppercase text-[13px]" style={{ WebkitTextStroke: '2px #000', paintOrder: 'stroke fill' }}>
        <span className="text-white">YOU</span>{' '}
        <span className="text-[#22c55e]">NEED</span>{' '}
        <span className="text-white">THIS</span>
      </span>
    ),
  },
  {
    id: 'cinematic',
    name: 'Cinematic',
    description: 'Spaced white, film subtitle',
    renderSubtitle: (
      <span className="font-medium text-white text-[12px]" style={{ letterSpacing: '0.18em', textShadow: '0 1px 3px rgba(0,0,0,0.9)' }}>
        A NEW ERA
      </span>
    ),
  },
  {
    id: 'highlight',
    name: 'Highlight',
    description: 'Marker-style background',
    renderSubtitle: (
      <span className="font-extrabold uppercase leading-relaxed text-[12px]" style={{ boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone' }}>
        <span className="bg-yellow-300 text-black px-1.5 py-0.5 rounded-sm">READ THIS</span>
      </span>
    ),
  },
]

// Compact caption preview tile: a small dark "stage" that shows just the
// styled caption text, the way it would look burned onto a clip. Much cleaner
// at thumbnail size than a full 9:16 mock.
function CaptionStage({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative h-14 rounded-lg overflow-hidden flex items-center justify-center px-2 bg-gradient-to-br from-[#1e293b] via-[#0f172a] to-[#020617]">
      <div className="absolute inset-0 opacity-[0.07] bg-[radial-gradient(circle_at_30%_20%,#fff,transparent_60%)]" />
      <div className="relative text-center leading-none">{children}</div>
    </div>
  )
}

export default function SubtitleStylePicker() {
  const { globalEffects, updateGlobalEffects } = useAppStore()
  const selectedStyle = globalEffects.subtitle_style || 'karaoke'

  const handleStyleChange = (styleId: string) => {
    updateGlobalEffects({ subtitle_style: styleId })
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Captions size={16} className="text-accent" />
        <span className="font-semibold text-slate-800 text-sm">Subtitle Style</span>
        <span className="ml-auto text-[11px] text-slate-400">Tap to apply</span>
      </div>

      {/* Always-visible gallery — no extra click needed */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5">
        {styles.map((style) => {
          const active = selectedStyle === style.id
          return (
            <button
              key={style.id}
              onClick={() => handleStyleChange(style.id)}
              className={`group relative text-left rounded-xl border p-2 transition-all ${
                active
                  ? 'bg-accent/10 border-accent/60 ring-2 ring-accent/25 shadow-sm'
                  : 'bg-surface-2 border-slate-200 hover:border-slate-300 hover:bg-slate-50'
              }`}
            >
              <CaptionStage>{style.renderSubtitle}</CaptionStage>
              {active && (
                <div className="absolute top-1.5 right-1.5 w-5 h-5 rounded-full bg-accent text-white flex items-center justify-center shadow">
                  <Check size={12} />
                </div>
              )}
              <div className="mt-2">
                <div className={`font-semibold text-[13px] leading-tight ${active ? 'text-accent' : 'text-slate-800'}`}>
                  {style.name}
                </div>
                <div className="text-[11px] leading-snug text-slate-500 truncate">{style.description}</div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}