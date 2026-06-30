import { useEffect, useState } from 'react'
import axios from 'axios'
import {
  Plus, Trash2, Edit2, X, Check,
  Users as UsersIcon, KeyRound, Globe, Clock,
} from 'lucide-react'
import { Account, useAppStore } from '../store/useAppStore'

interface PresetSummary {
  id: string; name: string; emoji: string; description: string
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
      id, name: id, emoji: '🎬', description: ''
    }

  return (
    <div className="max-w-4xl mx-auto p-8">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <UsersIcon size={22} className="text-accent" />
            Publishing Accounts
          </h1>
          <p className="text-slate-500 mt-1 text-sm">
            Each row pairs a YouTube identity (cookie file) with a content preset
            so the right rule-set fires automatically on publish.
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="btn btn-primary text-sm shrink-0"
        >
          <Plus size={14} /> New account
        </button>
      </div>

      {/* Active-account banner */}
      {activeAccountId !== 'default' && accounts.some(a => a.id === activeAccountId) && (
        <div className="card mb-4 border-accent/30 bg-accent/5 text-accent border text-sm flex items-center gap-2">
          <KeyRound size={14} />
          <span>
            Active publish target: <strong>{
              accounts.find(a => a.id === activeAccountId)?.name
            }</strong>{' '}
            ({badge(activeAccountId).emoji} {badge(activeAccountId).name})
          </span>
          <button
            onClick={() => setActiveAccountId('default')}
            className="ml-auto text-xs underline hover:no-underline"
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

      {/* List */}
      <div className="space-y-3">
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
  return (
    <div className={`card transition-colors ${
      isActive ? 'border-accent bg-accent/5' : 'border-slate-200'
    }`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-base font-semibold text-slate-900">
              {acc.name}
            </span>
            {isDefault && (
              <span className="text-[11px] text-slate-500 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded-md">
                system default
              </span>
            )}
            {isActive && !isDefault && (
              <span className="text-[11px] text-accent bg-accent/10 border border-accent/30 px-1.5 py-0.5 rounded-md font-medium">
                active for publish
              </span>
            )}
            <span className="text-[11px] text-slate-500 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded-md">
              {acc.platform}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3 text-xs">
            <div>
              <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-0.5 font-semibold flex items-center gap-1">
                <KeyRound size={9} /> Cookies
              </div>
              <div className="text-slate-700 truncate font-mono text-[11px]">
                {acc.cookies_path || (
                  <span className="text-slate-400 italic">not configured</span>
                )}
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-0.5 font-semibold flex items-center gap-1">
                <Globe size={9} /> Proxy
              </div>
              <div className="text-slate-700 truncate font-mono text-[11px]">
                {acc.proxy || (
                  <span className="text-slate-400 italic">none (deferred)</span>
                )}
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-0.5 font-semibold">
                Content preset
              </div>
              <div className="text-slate-700">
                <span className="inline-flex items-center gap-1">
                  <span aria-hidden>{badge.emoji}</span> {badge.name}
                </span>
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-0.5 font-semibold flex items-center gap-1">
                <Clock size={9} /> Last used
              </div>
              <div className="text-slate-700 text-[11px]">
                {acc.last_used_at || (
                  <span className="text-slate-400 italic">never</span>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-1.5 shrink-0">
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
          >
            <Edit2 size={12} /> Edit
          </button>
          {!isDefault && (
            <button
              onClick={onDelete}
              className="btn btn-secondary text-[11px] py-1 px-2 text-danger hover:bg-danger/10 border-danger/30"
            >
              <Trash2 size={12} /> Delete
            </button>
          )}
        </div>
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
        className="relative bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-lg w-full p-6 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-3 right-3 w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 flex items-center justify-center text-slate-500"
        >
          <X size={16} />
        </button>
        <h2 className="text-lg font-semibold text-slate-900">
          {initial ? 'Edit account' : 'New account'}
        </h2>

        <Field label="Name">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Anime Clips Daily"
            className="input w-full text-sm"
            disabled={initial?.id === 'default'}
          />
        </Field>

        <Field label="Platform">
          <select
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            className="input w-full text-sm"
          >
            <option value="youtube">YouTube</option>
            <option value="tiktok" disabled>TikTok (planned)</option>
          </select>
        </Field>

        <Field label="Cookies JSON path" hint="Absolute. Export from Firefox Cookie-Editor once, then paste here.">
          <input
            value={cookiesPath}
            onChange={(e) => setCookiesPath(e.target.value)}
            placeholder="C:\path\to\youtube_accounts\mychannel\cookies.json"
            className="input w-full text-sm font-mono"
          />
        </Field>

        <Field label="Proxy (optional)" hint="User-deferred step. UI accepts a socks5:// URL even though uploads run without it today.">
          <input
            value={proxy}
            onChange={(e) => setProxy(e.target.value)}
            placeholder="socks5://user:pw@host:1080"
            className="input w-full text-sm font-mono"
          />
        </Field>

        <Field label="Preferred content preset">
          <div className="grid grid-cols-2 gap-1.5">
            {presets.map((p) => {
              const sel = p.id === preferredPreset
              return (
                <button
                  key={p.id}
                  onClick={() => setPreferredPreset(p.id)}
                  className={`px-2.5 py-1.5 rounded-lg border text-left text-[12px] ${
                    sel
                      ? 'border-accent bg-accent/5 text-slate-800'
                      : 'border-slate-200 hover:border-slate-300 text-slate-500'
                  }`}
                >
                  <span className="font-semibold">{p.emoji} {p.name}</span>
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

        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="btn btn-secondary text-sm">
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={saving}
            className="btn btn-primary text-sm disabled:opacity-50"
          >
            {saving ? 'Saving…' : (initial ? 'Save' : 'Create')}
          </button>
        </div>
      </div>
    </div>
  )
}

function Field({
  label, hint, children,
}: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
        {label}
      </label>
      {children}
      {hint && <p className="text-[10px] text-slate-400 mt-1 leading-snug">{hint}</p>}
    </div>
  )
}

async function _delete(id: string, refresh: () => Promise<void>) {
  if (id === 'default') return  // UI never offers the button, defense-in-depth
  if (!confirm('Delete this account? Cookies file on disk is preserved.')) return
  await axios.delete(`/api/accounts/${id}`)
  await refresh()
}
