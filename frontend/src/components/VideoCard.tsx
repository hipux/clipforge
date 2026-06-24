import { Clock, Play, Tv, Video, Film } from 'lucide-react'

interface VideoInfo {
  id: string
  title: string
  duration: number
  thumbnail_url: string
  file_path: string
  platform: string
}

interface VideoCardProps {
  video: VideoInfo
}

const PlatformIcon = ({ platform }: { platform: string }) => {
  switch (platform.toLowerCase()) {
    case 'youtube': return <Play size={14} />
    case 'rutube': return <Tv size={14} />
    case 'vkvideo':
    case 'vk': return <Video size={14} />
    default: return <Film size={14} />
  }
}

const platformLabel: Record<string, string> = {
  youtube: 'YouTube',
  rutube: 'Rutube',
  vkvideo: 'VK Video',
  vk: 'VK Video',
}

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}

export default function VideoCard({ video }: VideoCardProps) {
  const platform = video.platform?.toLowerCase() || ''

  return (
    <div className="card flex gap-4 items-start">
      {/* Thumbnail */}
      {video.thumbnail_url ? (
        <img
          src={video.thumbnail_url}
          alt={video.title}
          className="w-32 h-[72px] object-cover rounded-lg shrink-0 border border-slate-200"
        />
      ) : (
        <div className="w-32 h-[72px] bg-surface-2 rounded-lg shrink-0 border border-slate-200 flex items-center justify-center">
          <Film size={24} className="text-slate-600" />
        </div>
      )}

      {/* Info */}
      <div className="flex-1 min-w-0">
        <h3 className="font-semibold text-slate-900 leading-snug line-clamp-2 text-sm">
          {video.title}
        </h3>
        <div className="flex items-center gap-3 mt-2">
          <span className="badge-accent">
            <PlatformIcon platform={platform} />
            {platformLabel[platform] || video.platform}
          </span>
          <span className="flex items-center gap-1 text-xs text-slate-500">
            <Clock size={11} />
            {formatDuration(video.duration)}
          </span>
        </div>
      </div>
    </div>
  )
}
