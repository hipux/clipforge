import { LucideIcon, LucideProps } from 'lucide-react'
import {
  // Content-type icons (score_breakdown.CONTENT_TYPE_ICON)
  Zap, Lightbulb, Smile, BookOpen, Flame, Music,
  Heart, HeartHandshake, Sparkles, Gamepad2, Clapperboard,
  // Preset icons (content_presets.PRESETS.icon)
  Mic,
  // Generic dashboard icons (publish presets & misc)
  Cloud, Layers, Hash,
} from 'lucide-react'

// Map of icon names emitted by the backend → lucide-react components.
// Keep this list SHORT — only icons the backend actually emits. The frontend
// is the source of truth for any icon used in the dashboard; the backend
// just sends a name.
const LIB: Record<string, LucideIcon> = {
  Zap, Lightbulb, Smile, BookOpen, Flame, Music,
  Heart, HeartHandshake, Sparkles, Gamepad2, Clapperboard,
  Mic, Cloud, Layers, Hash,
}

interface Props extends Omit<LucideProps, 'name'> {
  /** Stable enum string the backend sends (see IconLib). */
  name: string
  /** Optional fallback when `name` is unknown to LIB. Defaults to Clapperboard. */
  fallback?: LucideIcon
}

/**
 * Render a lucide-react icon by its string name — used by the dashboard to
 * honour `content_icon` (ScoreBreakdown) and `icon` (ContentPreset). Backend
 * NEVER hard-codes an emoji; the decision happens once on the frontend
 * keyed off a stable enum.
 *
 * Using this component (instead of inline `<X />`) means we never need to
 * touch the UI to add a new content type — extend `LIB` and the backend's
 * new name renders automatically.
 */
export default function IconByName({ name, fallback: Fallback = Clapperboard, ...rest }: Props) {
  const Resolved = LIB[name] ?? Fallback
  return <Resolved {...rest} />
}
