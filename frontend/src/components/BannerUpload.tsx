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

export default function BannerUpload() {
  const { globalEffects, updateGlobalEffects } = useAppStore()
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

      updateGlobalEffects({
        banner: {
          ...banner,
          enabled: true,
          banner_id: data.banner_id,
          url: data.url,
        },
      })
    } catch (err: any) {
      setUploadError(err.message || 'Upload failed')
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

  const handleToggle = () => {
    updateGlobalEffects({
      banner: {
        ...banner,
        enabled: !banner.enabled,
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

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <ImageIcon size={16} className="text-accent" />
          <h2 className="font-semibold text-slate-200">Banner / Watermark</h2>
        </div>
        {banner.url && (
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={banner.enabled}
              onChange={handleToggle}
              className="sr-only peer"
            />
            <div className="relative w-11 h-6 bg-slate-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-accent/50 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-accent"></div>
          </label>
        )}
      </div>

      {/* Upload section */}
      {!banner.url ? (
        <div>
          <label
            htmlFor="banner-upload"
            className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-slate-700 rounded-xl cursor-pointer hover:border-accent/50 hover:bg-accent/5 transition-all"
          >
            <div className="flex flex-col items-center justify-center py-4">
              <Upload size={24} className="text-slate-500 mb-2" />
              <p className="text-sm text-slate-400">
                {uploading ? 'Uploading...' : 'Click to upload banner'}
              </p>
              <p className="text-xs text-slate-600 mt-1">PNG, JPG, WebP · Max 5MB</p>
            </div>
            <input
              id="banner-upload"
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept="image/png,image/jpeg,image/jpg,image/webp"
              className="hidden"
              disabled={uploading}
            />
          </label>
          {uploadError && (
            <p className="text-xs text-red-400 mt-2">{uploadError}</p>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {/* Preview */}
          <div className="relative group">
            <img
              src={banner.url}
              alt="Banner preview"
              className="w-full h-32 object-contain rounded-lg bg-slate-900 border border-slate-700"
            />
            <button
              onClick={handleRemove}
              className="absolute top-2 right-2 w-7 h-7 bg-red-500/90 hover:bg-red-500 text-white rounded-lg flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <X size={14} />
            </button>
          </div>

          {/* Position selector */}
          <div>
            <label className="flex items-center gap-1.5 text-xs text-slate-400 mb-2">
              <MapPin size={12} />
              Position
            </label>
            <div className="grid grid-cols-3 gap-1.5">
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
