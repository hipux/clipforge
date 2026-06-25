import { useState } from 'react'
import { Captions, Check, ChevronDown } from 'lucide-react'
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
    description: 'Word-by-word yellow highlight. TikTok favorite.',
    renderSubtitle: (
      <span className="font-extrabold leading-tight tracking-tight text-[15px]" style={{ textShadow: '0 2px 5px rgba(0,0,0,0.85)' }}>
        <span className="text-white">THIS</span>{' '}
        <span className="text-yellow-300" style={{ textShadow: '0 0 10px rgba(250,204,21,0.85), 0 2px 4px rgba(0,0,0,0.9)' }}>CHANGES</span>{' '}
        <span className="text-white">IT</span>
      </span>
    ),
  },
  {
    id: 'neon',
    name: 'Neon',
    description: 'Glowing cyan letters, electric look.',
    renderSubtitle: (
      <span className="font-extrabold tracking-wide text-cyan-300 text-[15px]" style={{ textShadow: '0 0 8px #22d3ee, 0 0 16px #06b6d4, 0 0 28px #0891b2' }}>
        LET'S GO
      </span>
    ),
  },
  {
    id: 'hormozi',
    name: 'Hormozi',
    description: 'Bold caps, black stroke, green keyword pop.',
    renderSubtitle: (
      <span className="font-black leading-tight tracking-tight uppercase text-[15px]" style={{ WebkitTextStroke: '2.5px #000', paintOrder: 'stroke fill' }}>
        <span className="text-white">YOU</span>{' '}
        <span className="text-[#22c55e]">NEED</span>{' '}
        <span className="text-white">THIS</span>
      </span>
    ),
  },
  {
    id: 'highlight',
    name: 'Highlight',
    description: 'Marker-style background, clean & bold.',
    renderSubtitle: (
      <span className="font-extrabold uppercase leading-relaxed text-[13px]" style={{ boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone' }}>
        <span className="bg-yellow-300 text-black px-1.5 py-0.5 rounded-sm">READ THIS NOW</span>
      </span>
    ),
  },
]

// A realistic 9:16 "clip" mock used as the preview canvas. Uses the real video
// frame when available, otherwise a vibrant gradient + talking-head silhouette
// so it actually resembles one of our clips.
function ClipMock({ bg, children, large = false }: { bg?: string | null; children: React.ReactNode; large?: boolean }) {
  return (
    <div className={`relative w-full aspect-[9/16] overflow-hidden ${large ? 'rounded-xl' : 'rounded-lg'}`}>
      {bg ? (
        <img src={bg} alt="clip frame" className="absolute inset-0 w-full h-full object-cover" />
      ) : (
        <div className="absolute inset-0 bg-gradient-to-b from-[#243b55] via-[#141e30] to-[#0f2027]">
          <div className="absolute inset-0 bg-gradient-to-tr from-accent/10 via-transparent to-fuchsia-500/10" />
          <svg viewBox="0 0 200 360" className="absolute inset-0 w-full h-full opacity-[0.13]">
            <circle cx="100" cy="120" r="46" fill="#cbd5e1" />
            <path d="M20 360 Q100 210 180 360 Z" fill="#cbd5e1" />
          </svg>
        </div>
      )}
      {/* bottom scrim so captions are always legible */}
      <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/55 to-transparent" />
      <div className={`absolute left-0 right-0 flex justify-center px-2 text-center ${large ? 'bottom-6' : 'bottom-4'}`}>
        {children}
      </div>
    </div>
  )
}

export default function SubtitleStylePicker() {
  const { globalEffects, updateGlobalEffects, currentVideo, moments } = useAppStore()
  const selectedStyle = globalEffects.subtitle_style || 'karaoke'
  const [open, setOpen] = useState(false)

  const current = styles.find((s) => s.id === selectedStyle) || styles[0]
  const previewBg = moments.length > 0 ? moments[0].thumbnail_url : currentVideo?.thumbnail_url

  const handleStyleChange = (styleId: string) => {
    updateGlobalEffects({ subtitle_style: styleId })
    setOpen(false)
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <Captions size={16} className="text-accent" />
        <span className="font-semibold text-slate-800 text-sm">Subtitle Style</span>
      </div>

      {/* Trigger: shows current selection, opens the gallery */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3 rounded-xl border border-slate-200 bg-surface-2 p-2.5 hover:border-slate-300 hover:bg-slate-50 transition-all"
      >
        <div className="w-12 shrink-0">
          <ClipMock bg={previewBg}>{current.renderSubtitle}</ClipMock>
        </div>
        <div className="text-left flex-1 min-w-0">
          <div className="font-medium text-sm text-slate-800">{current.name}</div>
          <div className="text-[11px] leading-snug text-slate-500 truncate">{current.description}</div>
        </div>
        <span className="text-[11px] font-medium text-accent flex items-center gap-1 shrink-0">
          {open ? 'Close' : 'Choose subtitles'}
          <ChevronDown size={14} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
        </span>
      </button>

      {/* Gallery */}
      {open && (
        <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {styles.map((style) => {
            const active = selectedStyle === style.id
            return (
              <button
                key={style.id}
                onClick={() => handleStyleChange(style.id)}
                className={`group text-left rounded-xl border transition-all overflow-hidden ${
                  active
                    ? 'bg-accent/10 border-accent/50 ring-2 ring-accent/25'
                    : 'bg-surface-2 border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                }`}
              >
                <div className="relative">
                  <ClipMock bg={previewBg} large>{style.renderSubtitle}</ClipMock>
                  {active && (
                    <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-accent text-white flex items-center justify-center shadow">
                      <Check size={13} />
                    </div>
                  )}
                </div>
                <div className="px-2.5 pb-2.5 pt-2">
                  <div className={`font-semibold text-sm mb-0.5 ${active ? 'text-accent' : 'text-slate-800'}`}>
                    {style.name}
                  </div>
                  <div className="text-[11px] leading-snug text-slate-500">{style.description}</div>
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}