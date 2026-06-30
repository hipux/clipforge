import { forwardRef, SelectHTMLAttributes, useId } from 'react'
import { ChevronDown } from 'lucide-react'

type Props = SelectHTMLAttributes<HTMLSelectElement> & {
  /** Optional fixed width — defaults to w-full so it matches sibling <input>s. */
  block?: boolean
}

/**
 * A `<select>` that looks like the rest of the form (same border-radius,
 * same focus ring as `.input`). The native chevron is hidden via
 * `appearance: none` and replaced with a Lucide `ChevronDown` so it
 * actually picks up theme color and works in dark mode.
 *
 * Keyboard, accessibility and option styling remain 100% native — this
 * is purely cosmetic.
 */
const Select = forwardRef<HTMLSelectElement, Props>(function Select(
  { block = true, className = '', children, ...rest }, ref,
) {
  const id = useId()
  return (
    <div className={`relative ${block ? 'w-full' : ''}`}>
      <select
        ref={ref}
        id={id}
        {...rest}
        className={[
          // native = "input" base + native chrome stripped + select-friendly tweaks.
          'bg-white border border-slate-300 rounded-xl px-4 py-2.5',
          'text-slate-900 placeholder-slate-400',
          'outline-none ring-1 ring-transparent',
          'focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/30',
          'transition-all duration-150',
          // Hide the OS chevron so our overlay ChevronDown is the only one.
          'appearance-none [-webkit-appearance:none] [-moz-appearance:none]',
          // Reserve room on the right for the chevron icon.
          'pr-10',
          // Disabled / invalid styling parity with regular inputs.
          'disabled:bg-slate-50 disabled:text-slate-400 disabled:cursor-not-allowed',
          className,
        ].join(' ')}
      >
        {children}
      </select>
      {/* Pure decoration — the underlying <select> still owns focus and
          keyboard nav, so we mark the icon aria-hidden and pointer-events-none. */}
      <ChevronDown
        size={16}
        aria-hidden="true"
        className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
      />
    </div>
  )
})

export default Select
