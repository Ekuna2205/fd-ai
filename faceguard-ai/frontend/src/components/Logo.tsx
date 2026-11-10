export function Logo({ compact }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <svg viewBox="0 0 32 32" className="size-8 shrink-0" aria-hidden={!compact} role={compact ? 'img' : undefined} aria-label={compact ? 'FaceGuard AI' : undefined}>
        <rect width="32" height="32" rx="8" fill="#111B2D" />
        <path d="M16 5 6 9v7c0 5.5 4.2 9.6 10 11 5.8-1.4 10-5.5 10-11V9L16 5Z" fill="none" stroke="#22D3EE" strokeWidth="2" />
        <circle cx="16" cy="15" r="3" fill="#22D3EE" />
      </svg>
      <span className={`whitespace-nowrap text-[15px] font-semibold tracking-tight ${compact ? 'hidden sm:inline' : ''}`}>FaceGuard AI</span>
    </div>
  )
}
