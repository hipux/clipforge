import { useEffect, useState } from 'react'
import axios from 'axios'
import {
  Plus, Trash2, Edit2, X, Check, CheckCircle2,
  Users as UsersIcon, KeyRound, Globe, Clock,
  Video, Sparkles, Tv,
} from 'lucide-react'
import { Account, useAppStore } from '../store/useAppStore'
import IconByName from '../components/IconByName'
import Select from '../components/Select'

interface PresetSummary {
  id: string; name: string; icon: string; description: string
}

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [presets, setPresets] = useState<PresetSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const { activeAccountId, setActiveAccountId } = useAppStore()

  const refresh = async () => {
    try {
      const [accRes, presRes] = await Promise.all([
        axios.get('/api/accounts'),
        axios.get('/api/moments/presets'),
      ])
      setAccounts(accRes.data)
      setPresets(presRes.data)
      setError(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load accounts')
    }
  }

  useEffect(() => { refresh() }, [])

  // Helper to render the preset badge inline.
  const badge = (id: string) =>
    presets.find((p) => p.id === id) ?? {
      id, name: id, icon: 'Clapperboard', description: ''
    }

  const active = accounts.find((a) => a.id === activeAccountId)
  const otherCount = accounts.filter((a) => a.id !== activeAccountId).length

  return (
    <div className="max-w-5xl mx-auto p-8">
      {/* Header — one tight row with actionable "New account" on the right */}
      <div className="mb-6 flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <UsersIcon size={22} className="text-accent" />
            Publishing Accounts
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            {accounts.length === 0
              ? 'No accounts yet — create one to start publishing.'
              : <>{active && <span className="text-slate-700 font-medium">{active.name}</span>}
                 {active && <span className="mx-1.5 text-slate-300">·</span>}
                 <span>{otherCount} other{otherCount === 1 ? '' : 's'}</span></>}
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="btn btn-primary text-sm shrink-0"
        >
          <Plus size={14} /> New account
        </button>
      </div>

      {/* Active-account banner — only shown if a non-default account is selected */}
      {activeAccountId !== 'default' && active && (
        <div className="card mb-4 border-accent/30 bg-accent/5 flex items-center gap-3">
          <CheckCircle2 size={18} className="text-accent shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-slate-800">
              Publishing to <span className="font-semibold">{active.name}</span>
            </div>
            <div className="text-xs text-slate-500 flex items-center gap-2 mt-0.5">
              <IconByName name={badge(active.preferred_preset).icon} size={10} className="text-slate-400" />
              <span>{badge(active.preferred_preset).name}</span>
              {active.last_used_at && (
                <>
                  <span className="text-slate-300">·</span>
                  <Clock size={10} className="text-slate-400" />
                  <span>last used {active.last_used_at}</span>
                </>
              )}
            </div>
          </div>
          <button
            onClick={() => setActiveAccountId('default')}
            className="text-xs text-slate-500 underline hover:no-underline shrink-0"
          >
            use default
          </button>
        </div>
      )}

      {/* Error toast */}
      {error && (
        <div className="card mb-4 border-danger/30 bg-danger/5 text-danger text-sm">
          {error}
        </div>
      )}

      {/* Empty state */}
      {accounts.length === 0 && (
        <div className="card text-center py-14 border-dashed">
          <UsersIcon size={32} className="text-slate-400 mx-auto mb-3" />
          <h3 className="font-semibold text-slate-700 mb-1">No accounts yet</h3>
          <p className="text-slate-500 text-sm mb-4">
            Create one to keep cookies + a content preset together.
          </p>
          <button onClick={() => setShowCreate(true)} className="btn btn-primary text-sm">
            <Plus size={14} /> Create your first account
          </button>
        </div>
      )}

      {/* List — 12-col grid: cards get a clean status column */}
      {accounts.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {accounts.map((acc) => (
            <AccountRow
              key={acc.id}
              acc={acc}
              badge={badge(acc.preferred_preset)}
              isActive={acc.id === activeAccountId}
              isDefault={acc.id === 'default'}
              onActivate={() => setActiveAccountId(acc.id)}
              onEdit={() => setEditingId(acc.id)}
              onDelete={() => _delete(acc.id, refresh)}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      {showCreate && (
        <AccountEditor
          presets={presets}
          onClose={() => setShowCreate(false)}
          onSave={async (body) => {
            await axios.post('/api/accounts', body)
            setShowCreate(false)
            refresh()
          }}
        />
      )}
      {editingId && (
        <AccountEditor
          initial={accounts.find((a) => a.id === editingId)!}
          presets={presets}
          onClose={() => setEditingId(null)}
          onSave={async (body) => {
            await axios.patch(`/api/accounts/${editingId}`, body)
            setEditingId(null)
            refresh()
          }}
        />
      )}
    </div>
  )
}

// ─── Row ─────────────────────────────────────────────────────────────────────

function statusFor(acc: Account): { label: string; tone: 'ok' | 'warn' | 'idle' } {
  // Operator signal: cookies file configured? recently used? or untouched?
  if (acc.id === 'default') return { label: 'system default', tone: 'idle' }
  if (!acc.cookies_path) return { label: 'no cookies configured', tone: 'warn' }
  if (acc.last_used_at) return { label: 'ready', tone: 'ok' }
  return { label: 'configured, never published', tone: 'warn' }
}

function AccountRow({
  acc, badge, isActive, isDefault, onActivate, onEdit, onDelete,
}: {
  acc: Account
  badge: PresetSummary
  isActive: boolean
  isDefault: boolean
  onActivate: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  const st = statusFor(acc)
  return (
    <div className={`card p-4 transition-all ${
      isActive ? 'ring-2 ring-accent border-transparent shadow-card-hover' : ''
    }`}>
      {/* Top row: name + status + actions */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[15px] font-semibold text-slate-900 truncate">
              {acc.name}
            </span>
            <StatusPill label={st.label} tone={st.tone} />
            {isActive && !isDefault && (
              <span className="text-[10px] text-accent bg-accent/10 border border-accent/30 px-1.5 py-0.5 rounded-md font-medium uppercase tracking-wider">
                active
              </span>
            )}
          </div>
          <div className="mt-1 flex items-center gap-1.5 text-xs text-slate-500">
            <PlatformIcon platform={acc.platform} size={11} className="text-slate-400" />
            <span className="capitalize">{acc.platform}</span>
            {acc.preferred_preset && (
              <>
                <span className="text-slate-300 mx-0.5">·</span>
                <IconByName name={badge.icon} size={10} className="text-slate-400" />
                <span>{badge.name}</span>
              </>
            )}
          </div>
        </div>

        <div className="flex gap-1 shrink-0">
          {!isActive && !isDefault && (
            <button
              onClick={onActivate}
              className="btn btn-primary text-[11px] py-1 px-2"
            >
              <Check size={12} /> Activate
            </button>
          )}
          <button
            onClick={onEdit}
            className="btn btn-secondary text-[11px] py-1 px-2"
            title="Edit"
          >
            <Edit2 size={12} />
          </button>
          {!isDefault && (
            <button
              onClick={onDelete}
              className="btn btn-secondary text-[11px] py-1 px-2 text-danger hover:bg-danger/10 border-danger/30"
              title="Delete"
            >
              <Trash2 size={12} />
            </button>
          )}
        </div>
      </div>

      {/* Bottom row: cookies + proxy paths */}
      <div className="mt-3 pt-3 border-t border-slate-100 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-[11px]">
        <DetailRow
          icon={<KeyRound size={10} className="text-slate-400" />}
          label="Cookies"
          value={acc.cookies_path}
          placeholder="not configured"
          mono
        />
        <DetailRow
          icon={<Globe size={10} className="text-slate-400" />}
          label="Proxy"
          value={acc.proxy}
          placeholder="none (deferred)"
          mono
        />
      </div>

      {acc.last_used_at && (
        <div className="mt-2 text-[10px] text-slate-400 flex items-center gap-1">
          <Clock size={10} /> Last used {acc.last_used_at}
        </div>
      )}
    </div>
  )
}

// ─── Small visual primitives ────────────────────────────────────────────────

function StatusPill({ label, tone }: { label: string; tone: 'ok' | 'warn' | 'idle' }) {
  const palette = {
    ok:   'bg-emerald-50 text-emerald-700 border-emerald-200',
    warn: 'bg-amber-50 text-amber-700 border-amber-200',
    idle: 'bg-slate-100 text-slate-500 border-slate-200',
  }[tone]
  // matching colour dot
  const dot = {
    ok:   'bg-emerald-500',
    warn: 'bg-amber-400',
    idle: 'bg-slate-400',
  }[tone]
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-wider font-medium px-1.5 py-0.5 rounded-md border ${palette}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  )
}

function PlatformIcon({ platform, ...props }: { platform: string; size?: number; className?: string }) {
  if (platform === 'youtube') return <Tv {...props} />
  if (platform === 'tiktok') return <Video {...props} />
  return <Sparkles {...props} />
}

function DetailRow({
  icon, label, value, placeholder, mono,
}: {
  icon: React.ReactNode
  label: string
  value: string | null
  placeholder: string
  mono?: boolean
}) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-slate-400 mb-0.5">
        {icon}{label}
      </div>
      <div className={`truncate ${mono ? 'font-mono' : ''} text-slate-700`}>
        {value || <span className="text-slate-400 italic">{placeholder}</span>}
      </div>
    </div>
  )
}

// ─── Modal editor (create + patch) ──────────────────────────────────────────

function AccountEditor({
  initial, presets, onClose, onSave,
}: {
  initial?: Account
  presets: PresetSummary[]
  onClose: () => void
  onSave: (body: {
    name: string; platform: string; cookies_path: string | null
    proxy: string | null; preferred_preset: string
  }) => Promise<void>
}) {
  const [name, setName] = useState(initial?.name ?? '')
  const [platform, setPlatform] = useState(initial?.platform ?? 'youtube')
  const [cookiesPath, setCookiesPath] = useState(initial?.cookies_path ?? '')
  const [proxy, setProxy] = useState(initial?.proxy ?? '')
  const [preferredPreset, setPreferredPreset] = useState(
    initial?.preferred_preset ?? 'default',
  )
  const [saveProxy, setSaveProxy] = useState(!initial)   // show proxy field only on create
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    if (!name.trim()) { setError('Name is required.'); return }
    setSaving(true); setError(null)
    try {
      await onSave({
        name: name.trim(),
        platform,
        cookies_path: cookiesPath.trim() || null,
        proxy: proxy.trim() || null,
        preferred_preset: preferredPreset,
      })
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Save failed')
      setSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="relative bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-2xl w-full overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-3 right-3 w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-500 z-10"
        >
          <X size={16} />
        </button>

        {/* Header band — keeps the modal visually anchored as a "form", not a popup */}
        <div className="px-6 py-5 border-b border-slate-100 bg-gradient-to-b from-slate-50 to-white">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center justify-center w-8 h-8 rounded-xl bg-accent/10 text-accent">
              <UsersIcon size={16} />
            </span>
            <h2 className="text-lg font-semibold text-slate-900">
              {initial ? 'Edit account' : 'New account'}
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-1 ml-10">
            Each row pairs a YouTube identity (cookie file) with a content preset.
          </p>
        </div>

        <div className="px-6 py-5 space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <Field label="Name" required>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Anime Clips Daily"
                className="input w-full text-sm"
                disabled={initial?.id === 'default'}
                autoFocus
              />
            </Field>

            <Field label="Platform">
              <Select
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                disabled={initial?.id === 'default' /* can't change default-row platform */}
              >
                <option value="youtube">YouTube</option>
                <option value="tiktok" disabled>TikTok (planned)</option>
              </Select>
            </Field>
          </div>

          <Field
            label="Cookies JSON path"
            hint="Absolute path. Export from Firefox Cookie-Editor once, then paste here. Leave empty to defer — you'll set it before publishing."
          >
            <input
              value={cookiesPath}
              onChange={(e) => setCookiesPath(e.target.value)}
              placeholder="C:\path\to\youtube_accounts\mychannel\cookies.json"
              className="input w-full text-sm font-mono"
            />
          </Field>

          {(!initial || saveProxy) && (
            <Field
              label="Proxy (optional)"
              hint={
                saveProxy
                  ? 'socks5:// or http:// URL. User-deferred step — uploads run without proxy today.'
                  : 'Click "Configure proxy" to set or change it for this account.'
              }
            >
              {!saveProxy ? (
                <button
                  type="button"
                  onClick={() => setSaveProxy(true)}
                  className="btn btn-secondary text-sm"
                >
                  Configure proxy
                </button>
              ) : (
                <div className="flex gap-2">
                  <input
                    value={proxy}
                    onChange={(e) => setProxy(e.target.value)}
                    placeholder="socks5://user:pw@host:1080"
                    className="input flex-1 text-sm font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => { setProxy(''); setSaveProxy(false) }}
                    className="btn btn-secondary text-sm"
                  >
                    Cancel
                  </button>
                </div>
              )}
            </Field>
          )}

          <Field label="Preferred content preset">
            <div className="grid grid-cols-2 gap-1.5">
              {presets.map((p) => {
                const sel = p.id === preferredPreset
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => setPreferredPreset(p.id)}
                    className={`px-3 py-2 rounded-xl border text-left text-[12px] transition-colors ${
                      sel
                        ? 'border-accent bg-accent/5 text-slate-900 shadow-sm'
                        : 'border-slate-200 hover:border-slate-300 text-slate-500'
                    }`}
                  >
                    <span className="inline-flex items-center gap-1.5 font-semibold">
                      <IconByName
                        name={p.icon} size={13}
                        className={sel ? 'text-accent' : 'text-slate-400'}
                      />
                      {p.name}
                    </span>
                    <div className="text-[10px] mt-0.5 leading-snug text-slate-500 line-clamp-2">
                      {p.description}
                    </div>
                  </button>
                )
              })}
            </div>
          </Field>

          {error && (
            <div className="text-xs text-danger bg-danger/5 border border-danger/20 rounded-md px-3 py-2">
              {error}
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50 flex justify-end gap-2">
          <button onClick={onClose} className="btn btn-secondary text-sm">
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={saving}
            className="btn btn-primary text-sm disabled:opacity-50"
          >
            {saving ? 'Saving…' : (initial ? 'Save changes' : 'Create account')}
          </button>
        </div>
      </div>
    </div>
  )
}

function Field({
  label, hint, required, children,
}: {
  label: string
  hint?: string
  required?: boolean
  children: React.ReactNode
}) {
  return (
    <div>
      <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
        {label}
        {required && <span className="text-danger ml-0.5">*</span>}
      </label>
      {children}
      {hint && <p className="text-[10px] text-slate-400 mt-1.5 leading-snug">{hint}</p>}
    </div>
  )
}

async function _delete(id: string, refresh: () => Promise<void>) {
  if (id === 'default') return  // UI never offers the button, defense-in-depth
  if (!confirm('Delete this account? Cookies file on disk is preserved.')) return
  await axios.delete(`/api/accounts/${id}`)
  await refresh()
}
