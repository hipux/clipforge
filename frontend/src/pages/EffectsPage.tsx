import { useNavigate } from 'react-router-dom'
import { useAppStore } from '../store/useAppStore'
import EffectToggle from '../components/EffectToggle'
import BannerUpload from '../components/BannerUpload'
import SubtitleStylePicker from '../components/SubtitleStylePicker'
import {
  Sliders,
  Layers,
  FlipHorizontal,
  Palette,
  Info,
  ArrowRight,
  ArrowLeft,
} from 'lucide-react'

const effectConfig = [
  {
    key: 'blur_background' as const,
    icon: <Layers size={18} />,
    label: 'Blurred Background',
    description: 'Scale to 9:16 vertical format with blurred background fill',
  },
  {
    key: 'mirror' as const,
    icon: <FlipHorizontal size={18} />,
    label: 'Mirror Effect',
    description: 'Horizontal flip of the video (hflip)',
  },
  {
    key: 'color_correction' as const,
    icon: <Palette size={18} />,
    label: 'Color Enhancement',
    description: 'Subtle boost: +1% brightness, +1% contrast, +2% saturation',
  },
]

export default function EffectsPage() {
  const navigate = useNavigate()
  const { selectedMomentIds, globalEffects, updateGlobalEffects } = useAppStore()

  if (selectedMomentIds.length === 0) {
    navigate('/moments')
    return null
  }

  const enabledCount = Object.values(globalEffects).filter(Boolean).length

  return (
    <div className="max-w-xl mx-auto p-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-2 text-accent text-xs font-semibold uppercase tracking-widest mb-2">
          <span className="w-4 h-px bg-accent" />
          Step 3 of 5
        </div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <Sliders size={22} className="text-accent" />
          Configure Effects
        </h1>
        <p className="text-slate-500 mt-1 text-sm">
          Choose which effects to apply to your{' '}
          <span className="text-slate-300 font-medium">{selectedMomentIds.length} clip{selectedMomentIds.length !== 1 ? 's' : ''}</span>.
        </p>
      </div>

      {/* Subtitle style picker */}
      <div className="mb-5">
        <SubtitleStylePicker />
      </div>

      {/* Effects list */}
      <div className="card mb-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-slate-200">Video Effects</h2>
          <span className="badge-accent text-xs">
            {enabledCount} active
          </span>
        </div>
        <div className="space-y-2.5">
          {effectConfig.map((effect) => (
            <EffectToggle
              key={effect.key}
              icon={effect.icon}
              label={effect.label}
              description={effect.description}
              enabled={globalEffects[effect.key]}
              onToggle={() =>
                updateGlobalEffects({ [effect.key]: !globalEffects[effect.key] })
              }
            />
          ))}
        </div>
      </div>

      {/* Banner upload section */}
      <BannerUpload />

      {/* Info box */}
      <div className="flex items-start gap-3 px-4 py-3 rounded-xl bg-accent/6 border border-accent/20 mb-6 text-sm mt-5">
        <Info size={15} className="text-accent shrink-0 mt-0.5" />
        <div>
          <div className="font-medium text-slate-200 mb-1">Processing Info</div>
          <ul className="space-y-0.5 text-slate-400 text-xs leading-relaxed">
            <li>All effects are applied in a single FFmpeg pass — 100% local</li>
            <li>Subtitles use faster-whisper AI (runs on your machine, no cloud)</li>
            <li>~30–60 seconds per clip depending on effects enabled</li>
          </ul>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex justify-between items-center">
        <button
          onClick={() => navigate('/moments')}
          className="btn btn-secondary"
        >
          <ArrowLeft size={15} />
          Back
        </button>
        <button
          onClick={() => navigate('/process')}
          className="btn btn-primary px-6"
        >
          Start Processing
          <ArrowRight size={15} />
        </button>
      </div>
    </div>
  )
}
