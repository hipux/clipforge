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
  const { globalEffects, updateGlobalEffects, currentVideo, moments } = useAppStore()
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
      setUploadError('File too large (max 5MB)')
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
        throw new Error('Upload failed')
      }

      const data = await response.json()

      // Update global effects with banner info
      updateGlobalEffects({
        banner: {
          enabled: true,
          banner_id: data.banner_id,
          url: data.url,
          position: banner.position,
          size: banner.size,
          opacity: banner.opacity,
        },
      })
    } catch (err: any) {
      setUploadError(err.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleRemoveBanner = () => {
    updateGlobalEffects({
      banner: {
        ...banner,
        enabled: false,
        banner_id: undefined,
        url: undefined,
      },
    })
  }

  const handlePositionChange = (position: string) => {
    updateGlobalEffects({
      banner: {
        ...banner,
        position,
      },
    })
  }

  const handleSizeChange = (size: number) => {
    updateGlobalEffects({
      banner: {
        ...banner,
        size,
      },
    })
  }

  const handleOpacityChange = (opacity: number) => {
    updateGlobalEffects({
      banner: {
        ...banner,
        opacity,
      },
    })
  }

  // Use the first moment's thumbnail (9:16 with blurred background) or fallback to video thumbnail
  const previewBg = moments.length > 0 ? moments[0].thumbnail_url : currentVideo?.thumbnail_url

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <ImageIcon size={16} className="text-accent" />
        <span className="font-semibold text-slate-800 text-sm">Banner/Watermark</span>
      </div>

      {/* Upload / Preview */}
      <div className="space-y-3">
        {!banner.enabled || !banner.url ? (
          <div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileChange}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg border-2 border-dashed border-slate-200 hover:border-accent/40 hover:bg-accent/5 transition-colors text-sm text-slate-500 disabled:opacity-50"
            >
              <Upload size={16} />
              {uploading ? 'Uploading…' : 'Upload Banner Image'}
            </button>
            {uploadError && (
              <p className="text-xs text-danger mt-1.5">{uploadError}</p>
            )}
            <p className="text-xs text-slate-500 mt-1.5">
              PNG, JPG, WebP (max 5MB). Logo or watermark will overlay on each clip.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {/* Live Preview */}
            <div className="relative w-full aspect-[9/16] rounded-lg overflow-hidden border border-slate-200">
              {/* Background: moment thumbnail (9:16 with blur) if available, else video thumbnail or gradient */}
              {previewBg ? (
                <img 
                  src={previewBg} 
                  alt="Video frame" 
                  className="absolute inset-0 w-full h-full object-cover" 
                />
              ) : (
                <div className="absolute inset-0 bg-gradient-to-b from-[#1a1a2e] via-[#16213e] to-[#0f3460]" />
              )}

              {/* Banner overlay */}
              <img
                src={banner.url}
                alt="Banner preview"
                className={getPositionClasses(banner.position)}
                style={{
                  width: `${banner.size}%`,
                  opacity: banner.opacity / 100,
                }}
              />
            </div>

            {/* Remove button */}
            <button
              onClick={handleRemoveBanner}
              className="w-full btn btn-secondary text-xs"
            >
              <X size={12} />
              Remove Banner
            </button>
          </div>
        )}
      </div>

      {/* Banner controls (only when banner is active) */}
      {banner.enabled && banner.url && (
        <div className="mt-4 space-y-3 pt-3 border-t border-slate-200">
          {/* Position picker */}
          <div>
            <label className="flex items-center gap-1.5 text-xs text-slate-500 mb-2">
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
                      : 'bg-white border-slate-200 text-slate-500 hover:border-slate-300'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {/* Size slider */}
          <div>
            <label className="flex items-center justify-between text-xs text-slate-500 mb-2">
              <span>Size</span>
              <span className="text-slate-700 font-medium">{banner.size}% of width</span>
            </label>
            <input
              type="range"
              min="10"
              max="50"
              value={banner.size}
              onChange={(e) => handleSizeChange(Number(e.target.value))}
              className="w-full h-2 bg-slate-100 rounded-lg appearance-none cursor-pointer accent-accent"
            />
          </div>

          {/* Opacity slider */}
          <div>
            <label className="flex items-center justify-between text-xs text-slate-500 mb-2">
              <div className="flex items-center gap-1.5">
                <Palette size={12} />
                Opacity
              </div>
              <span className="text-slate-700 font-medium">{banner.opacity}%</span>
            </label>
            <input
              type="range"
              min="10"
              max="100"
              value={banner.opacity}
              onChange={(e) => handleOpacityChange(Number(e.target.value))}
              className="w-full h-2 bg-slate-100 rounded-lg appearance-none cursor-pointer accent-accent"
            />
          </div>
        </div>
      )}
    </div>
  )
}
