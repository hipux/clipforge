import {
  forwardRef, useCallback, useEffect, useId, useMemo, useRef, useState,
} from 'react'
import { ChevronDown, Check, Search, X } from 'lucide-react'

export interface Option<V> {
  value: V
  label: string
  /** Optional inline rendering of the option in the open menu. */
  icon?: React.ReactNode
  description?: string
  disabled?: boolean
}

// Split the prop shape into a discriminated union so a single-select
// consumer gets `(v: V) => void`, while multi-select gets
// `(vs: V[]) => void`. Without this, callers can't pass `setPlatform`
// because TS sees `V | V[]` and complains about setState's narrower type.
interface BaseProps<V> {
  options: Option<V>[]
  placeholder?: string
  disabled?: boolean
  full?: boolean
  searchableThreshold?: number
  open?: boolean
  onOpenChange?: (open: boolean) => void
  label?: string
  chevronClassName?: string
  variant?: 'default' | 'compact'
}
type Props<V> =
  | ({ multi?: false; value: V; onChange: (v: V) => void } & BaseProps<V>)
  | ({ multi: true;  value: V[]; onChange: (vs: V[]) => void } & BaseProps<V>)

const isV = <V,>(x: unknown): x is V => true

/**
 * Fully custom dropdown — none of the OS chrome `<select>` exposes.
 *
 *  - Trigger button with rotating chevron (180°) and matching `.input` border
 *  - Panel animates in via scale-y + opacity (no framer-motion dep — pure CSS)
 *  - Click-outside / Escape closes
 *  - Arrow keys navigate, Enter selects (Space toggles in multi), Home/End jump
 *  - Optional search filter (auto-shown once options.length > threshold)
 *  - Multi-select renders chip row in the trigger + checkmarks in the panel
 *
 * The API mirrors `<select value=... onChange=...>` so swap-in is a
 * class-name change at the call site.
 */
function CustomSelect<V extends string | number>(
  props: Props<V>,
  forwardedRef: React.Ref<HTMLDivElement>
) {
  const {
    value, onChange, options,
    multi = false,
    placeholder = 'Select…',
    disabled = false,
    full = true,
    searchableThreshold = 8,
    open: openProp, onOpenChange,
    label, chevronClassName,
    variant = 'default',
  } = props

  const generatedId = useId()
  const rootRef = useRef<HTMLDivElement | null>(null)
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  const searchRef = useRef<HTMLInputElement | null>(null)
  // Flip panel above the trigger when there's not enough room below —
  // prevents the panel from being clipped by the parent modal's
  // overflow:hidden.
  const [flipUp, setFlipUp] = useState(false)

  // Use a callback ref pair — one for our internal state and one for the
  // forwarded ref. We can't mix ref= assignments (forwardedRef is read-only),
  // so the parent merges both functions in the JSX below.
  const setRootEl = useCallback((el: HTMLDivElement | null) => {
    rootRef.current = el
    if (typeof forwardedRef === 'function') forwardedRef(el)
    else if (forwardedRef) (forwardedRef as React.MutableRefObject<HTMLDivElement | null>).current = el
  }, [forwardedRef])

  const [open, setOpen] = useState(false)
  // Sync controlled open, if caller passes open/onOpenChange.
  useEffect(() => {
    if (openProp !== undefined) setOpen(openProp)
  }, [openProp])

  const [highlight, setHighlight] = useState<number>(0)
  const [query, setQuery] = useState('')

  // Focus search when menu opens (if searchable).
  useEffect(() => {
    if (open && options.length >= searchableThreshold) {
      // The search input is a child of the menu — focus after mount.
      requestAnimationFrame(() => searchRef.current?.focus())
    }
  }, [open, options.length, searchableThreshold])

  // Flip-above logic. When the open menu is positioned below the
  // trigger and would clip against the viewport / a parent with
  // overflow:hidden, render it upward instead. We walk up the
  // ancestor chain to find the nearest overflow ancestor — that
  // ancestor's clipping rect tells us when to flip.
  useEffect(() => {
    if (!open) { setFlipUp(false); return }
    const root = rootRef.current
    if (!root) return
    const triggerRect = root.getBoundingClientRect()
    // Approximate menu height. Conservative — even with 10 options, the
    // panel never grows past 280px because of max-h-64.
    const menuHeightGuess = 280

    // Walk up the DOM to find an ancestor that DOES clip its contents
    // (overflow != visible). That's our true ceiling.
    function findClipAncestor(el: HTMLElement | null): HTMLElement | null {
      let cur = el?.parentElement ?? null
      while (cur && cur !== document.body) {
        const cs = getComputedStyle(cur)
        if (cs.overflow !== 'visible' && cs.overflowX !== 'visible') {
          return cur
        }
        cur = cur.parentElement
      }
      return null
    }
    const clipEl = findClipAncestor(root)
    const clipRect = clipEl ? clipEl.getBoundingClientRect() : null
    const aboveRect = clipRect ?? {
      top: 0,
      bottom: window.innerHeight,
    }
    const below = triggerRect.bottom + 4 + menuHeightGuess
    const viewportBottom = aboveRect.bottom
    // If menu overflows the clipper, flip. Aim for 16px of breathing room.
    setFlipUp(below > viewportBottom - 16)
  }, [open, options.length])

  // Compute selected values as a normalized Set for fast lookup.
  const selected: Set<V> = useMemo(() => {
    if (multi) return new Set<V>(value as V[])
    return new Set<V>([value as V])
  }, [value, multi])

  const filtered = useMemo(() => {
    if (!query.trim()) return options
    const q = query.toLowerCase()
    return options.filter(
      (o) =>
        o.label.toLowerCase().includes(q) ||
        (o.description?.toLowerCase().includes(q) ?? false)
    )
  }, [options, query])

  const commit = useCallback(
    (v: V) => {
      if (multi) {
        const cur = Array.isArray(value) ? [...(value as V[])] : []
        const idx = cur.findIndex((x) => Object.is(x, v))
        let next: V[]
        if (idx >= 0) next = cur.filter((_, i) => i !== idx)
        else next = [...cur, v]
        ;(onChange as (vs: V[]) => void)(next)
        setHighlight(0)
        setOpen(true)  // keep panel open so you can pick more
      } else {
        ;(onChange as (v: V) => void)(v)
        setOpen(false)
        onOpenChange?.(false)
      }
    }, [multi, onChange, value, onOpenChange]
  )

  const onKeyDownTrigger = (ev: React.KeyboardEvent) => {
    if (disabled) return
    if (ev.key === 'Enter' || ev.key === ' ' || ev.key === 'ArrowDown') {
      ev.preventDefault()
      setOpen(true)
      onOpenChange?.(true)
      setHighlight(0)
    } else if (ev.key === 'ArrowUp') {
      ev.preventDefault()
      setOpen(true)
      onOpenChange?.(true)
      setHighlight(Math.max(0, options.length - 1))
    }
  }

  const onKeyDownPanel = (ev: React.KeyboardEvent) => {
    if (ev.key === 'ArrowDown') {
      ev.preventDefault()
      setHighlight((h) => Math.min(filtered.length - 1, h + 1))
    } else if (ev.key === 'ArrowUp') {
      ev.preventDefault()
      setHighlight((h) => Math.max(0, h - 1))
    } else if (ev.key === 'Home') {
      ev.preventDefault()
      setHighlight(0)
    } else if (ev.key === 'End') {
      ev.preventDefault()
      setHighlight(filtered.length - 1)
    } else if (ev.key === 'Enter' || ev.key === ' ') {
      ev.preventDefault()
      const opt = filtered[highlight]
      if (opt && !opt.disabled) commit(opt.value)
    }
  }

  // ── Trigger display ────────────────────────────────────────────────────────
  const triggerLabel = useMemo(() => {
    if (multi) {
      const sel = options.filter((o) => selected.has(o.value))
      if (sel.length === 0) return <span className="text-slate-400">{placeholder}</span>
      if (sel.length === 1) {
        return (
          <span className="inline-flex items-center gap-1.5 truncate">
            {sel[0].icon}
            <span className="truncate">{sel[0].label}</span>
            {sel[0].description && (
              <span className="text-slate-400 text-[11px] truncate">{sel[0].description}</span>
            )}
          </span>
        )
      }
      // N selected — render as inline chip row + count
      return (
        <span className="inline-flex items-center gap-1 truncate">
          {sel.slice(0, 2).map((o) => (
            <span key={String(o.value)}
              className="inline-flex items-center gap-1 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded text-[11px] text-slate-700">
              {o.icon}
              <span>{o.label}</span>
            </span>
          ))}
          {sel.length > 2 && (
            <span className="text-[11px] text-slate-500">+{sel.length - 2}</span>
          )}
        </span>
      )
    }
    const sel = options.find((o) => selected.has(o.value))
    if (!sel) return <span className="text-slate-400">{placeholder}</span>
    return (
      <span className="inline-flex items-center gap-1.5 truncate">
        {sel.icon}
        <span className="truncate">{sel.label}</span>
        {sel.description && (
          <span className="text-slate-400 text-[11px] truncate">{sel.description}</span>
        )}
      </span>
    )
  }, [multi, options, placeholder, selected])

  const compact = variant === 'compact'

  return (
    <div ref={setRootEl} className={`relative ${full ? 'w-full' : ''} ${label ? 'block' : ''}`}>
      {label && (
        <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
          {label}
        </label>
      )}
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => {
          if (disabled) return
          setOpen((o) => !o)
          onOpenChange?.(!open)
          setHighlight(0)
        }}
        onKeyDown={onKeyDownTrigger}
        className={[
          // base classes, mirror `.input`
          'group w-full flex items-center justify-between gap-2 text-left',
          compact ? 'h-9 px-3 text-[13px]' : 'min-h-[44px] px-4 py-2.5 text-sm',
          'bg-white border border-slate-300 rounded-xl',
          'text-slate-900',
          'outline-none ring-1 ring-transparent',
          'transition-all duration-150',
          // colour the placeholder / muted text via the inner span
          'focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/30',
          open ? 'border-indigo-500 ring-2 ring-indigo-500/30' : '',
          disabled ? 'bg-slate-50 text-slate-400 cursor-not-allowed' : 'hover:border-slate-400',
        ].join(' ')}
      >
        <span className="flex-1 min-w-0 truncate">
          {triggerLabel}
        </span>
        <ChevronDown
          size={compact ? 14 : 16}
          aria-hidden="true"
          className={[
            'shrink-0 text-slate-400 transition-transform duration-200 ease-out',
            open ? 'rotate-180 text-accent' : '',
            chevronClassName ?? '',
          ].join(' ')}
        />
      </button>

      {/* Panel — pure CSS animation; rendered unconditionally so the
          transform can interpolate from the measured hidden state. The
          `pointer-events-none` while closed still allows focus inside for
          search keyboard flow only when open. */}
      <div
        role="listbox"
        aria-disabled={disabled}
        className={[
          'absolute left-0 right-0 z-40 origin-top',
          // flush against the trigger edge — earlier mt-1.5 produced an
          // awkward white gap that read as visual misalignment between the
          // button and the panel.
          flipUp ? 'bottom-full mb-0' : 'top-full mt-0',
          full ? '' : 'min-w-[16rem]',
          'bg-white border border-slate-200 rounded-xl shadow-xl',
          'overflow-hidden',
          // animation: scale-y + opacity. Flip the transform origin so the
          // menu grows downward visually when it renders above us.
          'transition-all duration-150 ease-out',
          open
            ? 'opacity-100 scale-y-100 pointer-events-auto'
            : 'opacity-0 pointer-events-none',
          flipUp ? 'origin-bottom' : 'origin-top',
        ].join(' ')}
        onKeyDown={onKeyDownPanel}
        tabIndex={open ? 0 : -1}
        style={{ transform: open ? 'scaleY(1)' : (flipUp ? 'scaleY(0.95)' : 'scaleY(0.95)') }}
      >
        {/* Search */}
        {options.length >= searchableThreshold && (
          <div className="px-2 py-2 border-b border-slate-100 bg-slate-50/60">
            <div className="relative flex items-center">
              <Search size={13} className="absolute left-2.5 text-slate-400 pointer-events-none" />
              <input
                ref={searchRef}
                value={query}
                onChange={(e) => { setQuery(e.target.value); setHighlight(0) }}
                placeholder="Search…"
                className="w-full pl-7 pr-2 py-1.5 text-[13px] bg-white border border-slate-200 rounded-md outline-none focus:border-indigo-500"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => { setQuery(''); setHighlight(0) }}
                  className="absolute right-1.5 text-slate-400 hover:text-slate-700"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          </div>
        )}

        {/* Options list. Tighter vertical padding than before so the first
            option reads as 'flush' against the trigger-button edge — there's
            no awkward white strip above "YouTube" anymore. */}
        <div className="max-h-64 overflow-y-auto py-0.5">
          {filtered.length === 0 ? (
            <div className="px-3 py-6 text-center text-[12px] text-slate-400">
              No matches.
            </div>
          ) : filtered.map((opt, idx) => {
            const isSel = selected.has(opt.value)
            const isHL = idx === highlight && open
            return (
              <div
                key={String(opt.value)}
                role="option"
                aria-selected={isSel}
                aria-disabled={opt.disabled}
                onMouseEnter={() => setHighlight(idx)}
                onClick={() => { if (!opt.disabled) commit(opt.value) }}
                className={[
                  'group flex items-center gap-2 cursor-pointer select-none',
                  compact ? 'px-2.5 py-1.5 text-[13px]' : 'px-3 py-2 text-sm',
                  isHL ? 'bg-indigo-50' : '',
                  opt.disabled ? 'opacity-50 cursor-not-allowed' : '',
                ].join(' ')}
              >
                {opt.icon && <span className="shrink-0 text-slate-500">{opt.icon}</span>}
                <span className="flex-1 min-w-0 truncate">
                  <span className="font-medium text-slate-800">{opt.label}</span>
                  {opt.description && (
                    <span className="ml-2 text-[11px] text-slate-400">{opt.description}</span>
                  )}
                </span>
                {isSel && (
                  <Check size={14} className="shrink-0 text-accent" />
                )}
              </div>
            )
          })}
        </div>

        {multi && (
          <div className="px-3 py-2 border-t border-slate-100 bg-slate-50/60 text-[11px] text-slate-500 flex justify-between">
            <span>{selected.size} selected</span>
            {selected.size > 0 && (
              <button
                type="button"
                className="text-slate-500 hover:text-danger"
                onClick={() => (onChange as (vs: V[]) => void)([])}
              >
                Clear all
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// Plain type-erased forwardRef. The cast at the bottom is necessary because
// forwardRef + generics require a forwardRef factory signature that TypeScript
// can't infer for V-bound components.
const _CustomSelect = forwardRef(CustomSelect) as <V extends string | number>(
  props: Props<V> & { ref?: React.Ref<HTMLDivElement> }
) => React.ReactElement

export default _CustomSelect

// Helps tree-shake: export the un-typed Options helper so consumers
// don't repeat its shape everywhere.
export type CustomSelectOption<V> = Option<V>
