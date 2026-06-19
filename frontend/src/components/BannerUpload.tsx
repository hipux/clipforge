import { useState, useRef } from 'react'
import { Upload, Image as ImageIcon, X, MapPin, Palette } from 'lucide-react'
import { useAppStore } from '../store/useAppStore'

const positionOptions = [
  { value: 'top-left', label: 'Top Left' },
  { value: 'top-center', label: 'Top Center' },
  { value: 'top-right', label: 'Top Right' },
  { value: 'bottom-left', label: 'Bottom Left' },
  { value: 'bottom-center', label: 'Bottom Center' },
  { value: 'bottom-right', label: 'Bottom Right' },
]

const getPositionClasses = (position: string) => {
  const map: Record<string, string> = {
    'top-left': 'absolute top-2 left-2',
    'top-center': 'absolute top-2 left-1/2 -translate-x-1/2',
    'top-right': 'absolute top-2 right-2',
    'bottom-left': 'absolute bottom-2 left-2',
    'bottom-center': 'absolute bottom-2 left-1/2 -translate-x-1/2',
    'bottom-right': 'absolute bottom-2 right-2',
  }
  return map[position] || 'absolute top-2 right-2'
}

export default function BannerUpload() {
  const { globalEffects, updateGlobalEffects, currentVideo } = useAppStore()
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const banner = globalEffects.banner || {
    enabled: false,
    position: 'top-right',
    size: 20,
    opacity: 80,
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Validate file type
    if (!file.type.startsWith('image/')) {
      setUploadError('Please select an image file (PNG, JPG, WebP)')
      return
    }

    // Validate file size (5MB)
    if (file.size > 5 * 1024 * 1024) {
      setUploadError('File too large. Maximum size is 5MB')
      return
    }

    setUploading(true)
    setUploadError(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch('/api/upload/banner', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Upload failed')
      }

      const data = await response.json()

      // Update global effects with banner
      updateGlobalEffects({
        banner: {
          ...banner,
          enabled: true,
          banner_id: data.banner_id,
          url: data.url,
        },
      })
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleRemove = () => {
    updateGlobalEffects({
      banner: {
        ...banner,
        enabled: false,
        banner_id: undefined,
        url: undefined,
      },
    })
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handlePositionChange = (position: string) => {
    updateGlobalEffects({
      banner: { ...banner, position },
    })
  }

  const handleSizeChange = (size: number) => {
    updateGlobalEffects({
      banner: { ...banner, size },
    })
  }

  const handleOpacityChange = (opacity: number) => {
    updateGlobalEffects({
      banner: { ...banner, opacity },
    })
  }

  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-4">
        <ImageIcon size={16} className="text-accent" />
        <h2 className="font-semibold text-slate-200">Banner Overlay</h2>
      </div>

      {/* Upload section */}
      {!banner.enabled && (
        <div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            className="hidden"
            id="banner-upload"
          />
          <label
            htmlFor="banner-upload"
            className="border-2 border-dashed border-slate-700 rounded-lg p-6 flex flex-col items-center justify-center cursor-pointer hover:border-slate-600 hover:bg-white/[0.02] transition-colors"
          >
            <Upload size={32} className="text-slate-500 mb-2" />
            <div className="text-sm text-slate-300 mb-1">
              {uploading ? 'Uploading...' : 'Click to upload banner'}
            </div>
            <div className="text-xs text-slate-500">PNG, JPG, WebP (max 5MB)</div>
          </label>
          {uploadError && <div className="text-xs text-red-400 mt-2">{uploadError}</div>}
        </div>
      )}

      {/* Preview section with video frame */}
      {banner.enabled && banner.url && (
        <div className="space-y-4">
          {/* Video frame preview with banner overlay */}
          <div className="relative">
            <div className="relative w-full aspect-video rounded-lg overflow-hidden group">
              {/* Background: thumbnail if available, else gradient */}
              {currentVideo?.thumbnail_url ? (
                <img 
                  src={currentVideo.thumbnail_url} 
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

              {/* PREVIEW badge */}
              <div className="text-[9px] font-bold uppercase tracking-wider text-white/40 bg-black/40 px-1.5 py-0.5 rounded absolute top-2 left-2 z-10">
                PREVIEW
              </div>

              {/* Banner overlay at selected position */}
              <img
                src={banner.url}
                alt="Banner"
                className={getPositionClasses(banner.position)}
                style={{
                  maxWidth: `${banner.size}%`,
                  opacity: banner.opacity / 100,
                }}
              />

              {/* Remove button (hover to reveal) */}
              <button
                onClick={handleRemove}
                className="absolute top-2 right-2 z-20 bg-red-500/90 hover:bg-red-600 text-white p-1.5 rounded-full transition-all opacity-0 group-hover:opacity-100"
                title="Remove banner"
              >
                <X size={14} />
              </button>
            </div>
          </div>

          {/* Position selector */}
          <div>
            <label className="flex items-center gap-1.5 text-xs text-slate-400 mb-2">
              <MapPin size={12} />
              Position
            </label>
            <div className="grid grid-cols-3 gap-2">
              {positionOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => handlePositionChange(option.value)}
                  className={`px-3 py-2 text-xs rounded-lg border transition-colors ${
                    banner.position === option.value
                      ? 'bg-accent/10 border-accent/40 text-accent'
                      : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {/* Size slider */}
          <div>
            <label className="flex items-center justify-between text-xs text-slate-400 mb-2">
              <span>Size</span>
              <span className="text-slate-300 font-medium">{banner.size}% of width</span>
            </label>
            <input
              type="range"
              min="10"
              max="50"
              value={banner.size}
              onChange={(e) => handleSizeChange(Number(e.target.value))}
              className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-accent"
            />
          </div>

          {/* Opacity slider */}
          <div>
            <label className="flex items-center justify-between text-xs text-slate-400 mb-2">
              <div className="flex items-center gap-1.5">
                <Palette size={12} />
                Opacity
              </div>
              <span className="text-slate-300 font-medium">{banner.opacity}%</span>
            </label>
            <input
              type="range"
              min="10"
              max="100"
              value={banner.opacity}
              onChange={(e) => handleOpacityChange(Number(e.target.value))}
              className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-accent"
            />
          </div>
        </div>
      )}
    </div>
  )
}
