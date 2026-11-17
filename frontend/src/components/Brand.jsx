import { Link } from "react-router-dom";

export function BrandMark({ className = "h-9 w-9" }) {
  return (
    <span className={`grid shrink-0 place-items-center rounded-xl bg-brand-600 ${className}`}>
      <svg viewBox="0 0 32 32" className="h-5 w-5" aria-hidden="true">
        <path d="M16 3.5 27 7.5v8.2c0 5.7-4.4 10.3-11 12.8-6.6-2.5-11-7.1-11-12.8V7.5L16 3.5Z" fill="#ffffff" />
        <path d="M16 9.5 21 11.2v3.6c0 2.5-2 4.5-5 5.6-3-1.1-5-3.1-5-5.6v-3.6L16 9.5Z" fill="#f47b20" />
      </svg>
    </span>
  );
}

export function Brand({ to = "/", light = false, compact = false }) {
  return (
    <Link to={to} className="flex items-center gap-2.5">
      <BrandMark />
      {!compact && (
        <span className={`font-display text-[17px] font-bold tracking-tight ${light ? "text-white" : "text-ink-950"}`}>
          Insure<span className={light ? "text-accent-300" : "text-accent-600"}>Connect</span>
        </span>
      )}
    </Link>
  );
}
