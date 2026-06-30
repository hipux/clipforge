import { useEffect, useState } from 'react'
import axios from 'axios'
import {
  Plus, Trash2, Edit2, X,
  Users as UsersIcon, Clock,
  Video, Sparkles, Tv,
  LayoutGrid, Rows3,
} from 'lucide-react'
import { Account, useAppStore } from '../store/useAppStore'
import IconByName from '../components/IconByName'
import CustomSelect from '../components/CustomSelect'

interface PresetSummary {
  id: string; name: string; icon: string; description: string
}

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [presets, setPresets] = useState<PresetSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const { accountViewMode, setAccountViewMode } = useAppStore()

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

  return (
    <div className="max-w-5xl mx-auto p-8">
      {/* Header — one tight row with view-mode toggle + actionable
          "New account" on the right. The toggle lives at the top because
          it changes how the entire list below is rendered. */}
      {/* Header — title + count on the left, primary "+ New account"
          action on the right. The view-mode toggle gets its own row
          below so it isn't competing with the primary button visually. */}
      <div className="mb-4 flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <UsersIcon size={22} className="text-accent" />
            Publishing Accounts
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            {accounts.length === 0
              ? 'No accounts yet — create one to start publishing.'
              : `${accounts.length} channel${accounts.length === 1 ? '' : 's'} configured`}
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="btn btn-primary text-sm shrink-0"
        >
          <Plus size={14} /> New account
        </button>
      </div>

      {/* View-mode sub-bar — sits between the title row and the list.
          Subdued weight: no accent fill on the active option, just a
          slightly darker background and bolder text. This way it reads
          as a layout choice, not a second action button. The choice
          persists across page reloads through the localStorage store. */}
      {accounts.length > 0 && (
        <div className="mb-4 flex items-center gap-1 text-xs">
          <span className="text-slate-400 mr-1">View</span>
          <button
            type="button"
            onClick={() => setAccountViewMode('table')}
            className={`inline-flex items-center gap-1.5 px-2 py-1 rounded transition-colors ${
              accountViewMode === 'table'
                ? 'bg-slate-100 text-slate-900 font-medium border border-slate-200'
                : 'text-slate-500 hover:text-slate-800'
            }`}
            title="Table view — best for many accounts"
          >
            <Rows3 size={12} /> Table
          </button>
          <button
            type="button"
            onClick={() => setAccountViewMode('cards')}
            className={`inline-flex items-center gap-1.5 px-2 py-1 rounded transition-colors ${
              accountViewMode === 'cards'
                ? 'bg-slate-100 text-slate-900 font-medium border border-slate-200'
                : 'text-slate-500 hover:text-slate-800'
            }`}
            title="Card view — best for a handful of accounts"
          >
            <LayoutGrid size={12} /> Cards
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

      {/* List — choose view-mode. Both share the same data and the
          same Edit/Delete actions; only the layout differs.
            • 'table' : semantic <table>.
            • 'cards' : 1–2 column tile grid; with 3 channels the tiles
              breathe and feel like an overview, whereas a table of 3
              rows looks thin and lonely.
          Both views are wrapped in a single <div> with a `key` bound
          to accountViewMode. The key forces React to unmount on view
          switch, which re-runs the `.view-swap` keyframe for a gentle
          crossfade (220ms ease-out, 4px slide-in). On the toggle
          itself: hover/active state has a 150ms color transition so
          the active option feels like it lights up rather than pops. */}
      {accounts.length > 0 && (
        <div key={accountViewMode} className="view-swap">
          {accountViewMode === 'table' ? (
            <div className="rounded-lg border border-slate-200 overflow-hidden bg-bg-elev">
              <table className="w-full text-sm">
                <thead className="bg-slate-50/80 border-b border-slate-200">
                  <tr>
                    <th className="py-2.5 pl-4 pr-3 text-left text-[10px] uppercase tracking-wider font-semibold text-slate-500">
                      Account
                    </th>
                    <th className="py-2.5 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-slate-500">
                      Platform
                    </th>
                    <th className="py-2.5 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-slate-500">
                      Content preset
                    </th>
                    <th className="py-2.5 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-slate-500">
                      Last used
                    </th>
                    <th className="py-2.5 px-3 text-left text-[10px] uppercase tracking-wider font-semibold text-slate-500">
                      Status
                    </th>
                    <th className="py-2.5 pr-4 pl-3 text-right text-[10px] uppercase tracking-wider font-semibold text-slate-500">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.map((acc) => (
                    <AccountRow
                      key={acc.id}
                      acc={acc}
                      badge={badge(acc.preferred_preset)}
                      isDefault={acc.id === 'default'}
                      onEdit={() => setEditingId(acc.id)}
                      onDelete={() => _delete(acc.id, refresh)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {accounts.map((acc) => (
                <AccountCard
                  key={acc.id}
                  acc={acc}
                  badge={badge(acc.preferred_preset)}
                  isDefault={acc.id === 'default'}
                  onEdit={() => setEditingId(acc.id)}
                  onDelete={() => _delete(acc.id, refresh)}
                />
              ))}
            </div>
          )}
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
  acc, badge, isDefault, onEdit, onDelete,
}: {
  acc: Account
  badge: PresetSummary
  isDefault: boolean
  onEdit: () => void
  onDelete: () => void
}) {
  const st = statusFor(acc)
  return (
    // Proper <tr> — semantic table-row, the whole row is the list-item.
    // Hover changes the row background so operators can scan a long
    // list of channels fast.
    <tr className="border-b border-slate-100 transition-colors hover:bg-slate-50/60">
      {/* Status dot + name combined for first column readability */}
      <td className="py-2.5 pl-4 pr-3 align-middle">
        <div className="flex items-center gap-2.5 min-w-0">
          <span
            className={`shrink-0 w-2 h-2 rounded-full ${
              st.tone === 'ok' ? 'bg-emerald-500' :
              st.tone === 'warn' ? 'bg-amber-400' : 'bg-slate-300'
            }`}
            title={st.label}
          />
          <div className="min-w-0">
            <div className="text-[14px] font-semibold text-slate-900 truncate flex items-center gap-1.5">
              {acc.name}
              {isDefault && (
                <span className="text-[10px] text-slate-400 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded-md font-normal">
                  default
                </span>
              )}
            </div>
            <div className="text-[10px] text-slate-400 mt-0.5 truncate" title={acc.cookies_path ?? ''}>
              {acc.cookies_path
                ? acc.cookies_path.split(/[\\/]/).slice(-1)[0]
                : <span className="italic">no cookies</span>}
            </div>
          </div>
        </div>
      </td>

      <td className="py-2.5 px-3 align-middle whitespace-nowrap">
        <span className="inline-flex items-center gap-1 text-[11px] text-slate-600">
          <PlatformIcon platform={acc.platform} size={11} />
          <span className="capitalize">{acc.platform}</span>
        </span>
      </td>

      <td className="py-2.5 px-3 align-middle whitespace-nowrap">
        <span className="inline-flex items-center gap-1.5 text-[11px] text-slate-700">
          <IconByName name={badge.icon} size={12} className="text-slate-500" />
          <span>{badge.name}</span>
        </span>
      </td>

      <td className="py-2.5 px-3 align-middle whitespace-nowrap text-[11px] text-slate-500">
        {acc.last_used_at
          ? <span className="inline-flex items-center gap-1"><Clock size={10} /> {acc.last_used_at}</span>
          : <span className="text-slate-400 italic">never</span>}
      </td>

      <td className="py-2.5 px-3 align-middle whitespace-nowrap">
        <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-wider font-medium px-1.5 py-0.5 rounded-md border ${
          st.tone === 'ok'   ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
        : st.tone === 'warn' ? 'bg-amber-50 text-amber-700 border-amber-200'
                            : 'bg-slate-100 text-slate-500 border-slate-200'
        }`}>
          {st.label}
        </span>
      </td>

      <td className="py-2.5 pr-4 pl-3 align-middle whitespace-nowrap">
        <div className="flex items-center justify-end gap-1">
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
      </td>
    </tr>
  )
}

// ─── Card view ───────────────────────────────────────────────────────────────
//
// Per-account tile. Used when accountViewMode === 'cards'. Two-column
// grid on tablet+, single column on mobile. Each tile is a self-contained
// card with status dot, name, platform+preset hint, cookies path preview,
// last-used, and the same Edit/Delete actions as the row view.

function AccountCard({
  acc, badge, isDefault, onEdit, onDelete,
}: {
  acc: Account
  badge: PresetSummary
  isDefault: boolean
  onEdit: () => void
  onDelete: () => void
}) {
  const st = statusFor(acc)
  return (
    <div className="card relative flex flex-col gap-2.5">
      {/* First row — status dot + name + platform + default chip */}
      <div className="flex items-start gap-2.5">
        <span
          className={`shrink-0 mt-1.5 w-2 h-2 rounded-full ${
            st.tone === 'ok' ? 'bg-emerald-500' :
            st.tone === 'warn' ? 'bg-amber-400' : 'bg-slate-300'
          }`}
          title={st.label}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="font-semibold text-slate-900 text-[15px] truncate">{acc.name}</span>
            {isDefault && (
              <span className="text-[10px] text-slate-400 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded-md font-normal">
                default
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5 mt-0.5 text-[11px] text-slate-500">
            <PlatformIcon platform={acc.platform} size={11} />
            <span className="capitalize">{acc.platform}</span>
            <span className="text-slate-300">·</span>
            <IconByName name={badge.icon} size={11} className="text-slate-400" />
            <span>{badge.name}</span>
          </div>
        </div>
      </div>

      {/* Cookies path preview */}
      <div className="text-[11px] font-mono text-slate-500 bg-slate-50 border border-slate-200 rounded-md px-2 py-1.5 truncate"
           title={acc.cookies_path ?? ''}>
        {acc.cookies_path
          ? acc.cookies_path
          : <span className="italic font-sans">no cookies set yet</span>}
      </div>

      {/* Footer — last-used + status pill + actions */}
      <div className="flex items-center justify-between gap-2 flex-wrap text-[11px]">
        <div className="flex items-center gap-2 text-slate-500">
          {acc.last_used_at
            ? <span className="inline-flex items-center gap-1"><Clock size={10} /> last used {acc.last_used_at}</span>
            : <span className="italic text-slate-400">never used</span>}
          <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-wider font-medium px-1.5 py-0.5 rounded-md border ${
            st.tone === 'ok'   ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
          : st.tone === 'warn' ? 'bg-amber-50 text-amber-700 border-amber-200'
                              : 'bg-slate-100 text-slate-500 border-slate-200'
          }`}>
            {st.label}
          </span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
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
    </div>
  )
}

// ─── Small visual primitives ────────────────────────────────────────────────

function PlatformIcon({ platform, ...props }: { platform: string; size?: number; className?: string }) {
  if (platform === 'youtube') return <Tv {...props} />
  if (platform === 'tiktok') return <Video {...props} />
  return <Sparkles {...props} />
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
        className="relative bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-2xl w-full"
        // NB: NO overflow-hidden. Earlier we clipped here so a
        // CustomSelect panel could extend outside the modal was cut by
        // this container. The panel now flips above the trigger
        // automatically, and we keep the rounded corners on the modal by
        // accepting that the panel's rounded panel sits in front.
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
              <CustomSelect
                value={platform}
                onChange={(v) => setPlatform(v)}
                disabled={initial?.id === 'default'}
                options={[
                  {
                    value: 'youtube',
                    label: 'YouTube',
                    icon: <Tv size={14} className="text-rose-500" />,
                    description: 'Channel via ytb-up cookies',
                  },
                  {
                    value: 'tiktok',
                    label: 'TikTok',
                    icon: <Video size={14} />,
                    description: 'planned — not yet wired',
                    disabled: true,
                  },
                ]}
              />
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
            <CustomSelect
              value={preferredPreset}
              onChange={(v) => setPreferredPreset(v)}
              options={presets.map((p) => ({
                value: p.id,
                label: p.name,
                description: p.description,
                icon: (
                  <IconByName name={p.icon} size={14} className="text-slate-500" />
                ),
              }))}
              searchableThreshold={1}
              multi={false}
            />
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
