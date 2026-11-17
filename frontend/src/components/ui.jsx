import { forwardRef, useEffect, useId, useRef } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Inbox,
  Loader2,
  Search,
  X,
} from "lucide-react";
import { STATUS_LABELS } from "../lib/constants";
import { titleize } from "../lib/format";

export function cn(...classes) {
  return classes.filter(Boolean).join(" ");
}

const buttonVariants = {
  primary: "bg-ink-950 text-white hover:bg-ink-900 shadow-sm",
  brand: "bg-brand-600 text-white hover:bg-brand-700 shadow-sm",
  accent: "bg-accent-500 text-white hover:bg-accent-600 shadow-sm",
  lime: "bg-lime-400 text-ink-950 hover:bg-lime-300 shadow-sm",
  secondary: "border border-ink-200 bg-white text-ink-800 hover:bg-ink-50",
  ghost: "text-ink-600 hover:bg-ink-100 hover:text-ink-900",
  danger: "bg-red-600 text-white hover:bg-red-700",
  "danger-soft": "border border-red-200 bg-red-50 text-red-700 hover:bg-red-100",
  dark: "bg-white/10 text-white hover:bg-white/15 border border-white/15",
};

const buttonSizes = {
  sm: "h-9 px-3 text-xs gap-1.5 rounded-lg",
  md: "h-11 px-4 text-sm gap-2 rounded-xl",
  lg: "h-12 px-5 text-sm gap-2 rounded-xl",
  icon: "h-10 w-10 rounded-xl",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  icon: Icon,
  className,
  children,
  disabled,
  ...props
}) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center font-semibold transition focus:outline-none focus-visible:ring-4 focus-visible:ring-brand-500/20 disabled:pointer-events-none disabled:opacity-50",
        buttonVariants[variant] || buttonVariants.primary,
        buttonSizes[size] || buttonSizes.md,
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : Icon ? <Icon className="h-4 w-4" /> : null}
      {children}
    </button>
  );
}

export function Field({ label, hint, error, required, children, className, htmlFor, describedBy }) {
  return (
    <div className={className}>
      {label && (
        <label htmlFor={htmlFor} className="label">
          {label} {required && <span className="text-red-500">*</span>}
        </label>
      )}
      {children}
      {error ? <p id={describedBy} className="mt-1.5 text-xs font-medium text-red-600">{error}</p> : hint ? <p id={describedBy} className="mt-1.5 text-xs text-ink-400">{hint}</p> : null}
    </div>
  );
}

export const Input = forwardRef(function Input({ label, hint, error, required, className, id, ...props }, ref) {
  const generatedId = useId();
  const inputId = id || generatedId;
  const describedBy = error || hint ? `${inputId}-hint` : undefined;
  return (
    <Field label={label} hint={hint} error={error} required={required} htmlFor={inputId} describedBy={describedBy}>
      <input
        ref={ref}
        id={inputId}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={describedBy}
        aria-required={required ? "true" : undefined}
        className={cn("control", error && "border-red-300 focus:border-red-500 focus:ring-red-500/10", className)}
        {...props}
      />
    </Field>
  );
});

export const Textarea = forwardRef(function Textarea({ label, hint, error, required, className, id, ...props }, ref) {
  const generatedId = useId();
  const inputId = id || generatedId;
  const describedBy = error || hint ? `${inputId}-hint` : undefined;
  return (
    <Field label={label} hint={hint} error={error} required={required} htmlFor={inputId} describedBy={describedBy}>
      <textarea
        ref={ref}
        id={inputId}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={describedBy}
        aria-required={required ? "true" : undefined}
        className={cn("control min-h-[110px] resize-y", error && "border-red-300", className)}
        {...props}
      />
    </Field>
  );
});

export const Select = forwardRef(function Select({ label, hint, error, required, options = [], placeholder, children, className, id, ...props }, ref) {
  const generatedId = useId();
  const inputId = id || generatedId;
  const describedBy = error || hint ? `${inputId}-hint` : undefined;
  return (
    <Field label={label} hint={hint} error={error} required={required} htmlFor={inputId} describedBy={describedBy}>
      <select
        ref={ref}
        id={inputId}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={describedBy}
        aria-required={required ? "true" : undefined}
        className={cn("control appearance-none bg-[length:16px] bg-[right_0.9rem_center] bg-no-repeat pr-9", className)}
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='none' stroke='%23587789' stroke-width='2' viewBox='0 0 24 24'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")",
        }}
        {...props}
      >
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((option) => {
          const value = typeof option === "string" ? option : option.value;
          const text = typeof option === "string" ? titleize(option) : option.label;
          return (
            <option key={value} value={value}>
              {text}
            </option>
          );
        })}
        {children}
      </select>
    </Field>
  );
});

export function SearchInput({ value, onChange, placeholder = "Search…", className, "aria-label": ariaLabel }) {
  return (
    <div className={cn("relative", className)}>
      <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
      <input type="search" value={value} onChange={onChange} placeholder={placeholder} aria-label={ariaLabel || placeholder} className="control pl-10" />
    </div>
  );
}

const toneClasses = {
  green: "bg-emerald-50 text-emerald-700 border-emerald-200",
  amber: "bg-amber-50 text-amber-700 border-amber-200",
  red: "bg-red-50 text-red-700 border-red-200",
  blue: "bg-sky-50 text-sky-700 border-sky-200",
  purple: "bg-violet-50 text-violet-700 border-violet-200",
  gray: "bg-ink-100 text-ink-600 border-ink-200",
};

const statusTones = {
  active: "green",
  approved: "green",
  succeeded: "green",
  completed: "green",
  verified: "green",
  paid: "green",
  selected: "green",
  policy_issued: "green",
  converted: "green",
  pending: "amber",
  submitted: "amber",
  under_review: "amber",
  processing: "amber",
  quoted: "amber",
  scheduled: "amber",
  requested: "amber",
  more_info: "amber",
  info_required: "amber",
  inspection_scheduled: "amber",
  assessment: "amber",
  received: "blue",
  draft: "gray",
  closed: "gray",
  expired: "gray",
  cancelled: "red",
  rejected: "red",
  failed: "red",
  suspended: "red",
  withdrawn: "red",
  lapsed: "red",
  refunded: "purple",
  in_progress: "blue",
};

export function Badge({ children, tone = "gray", className }) {
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold whitespace-nowrap", toneClasses[tone] || toneClasses.gray, className)}>
      {children}
    </span>
  );
}

export function StatusBadge({ status, label }) {
  const value = status || "pending";
  return <Badge tone={statusTones[value] || "gray"}>{label || STATUS_LABELS[value] || titleize(value)}</Badge>;
}

export function Spinner({ className = "h-5 w-5" }) {
  return <Loader2 className={cn("animate-spin text-brand-600", className)} />;
}

export function PageLoader({ label = "Loading workspace…" }) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3 text-sm text-ink-500">
      <Spinner className="h-7 w-7" />
      <span>{label}</span>
    </div>
  );
}

export function PageHeader({ eyebrow, title, description, actions, className }) {
  return (
    <div className={cn("mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div>
        {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
        <h1 className="font-display text-2xl font-bold tracking-tight text-ink-950 sm:text-3xl">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-500">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Stat({ icon: Icon, label, value, hint, tone = "brand", className }) {
  const tones = {
    brand: "bg-brand-50 text-brand-700",
    ink: "bg-ink-100 text-ink-700",
    amber: "bg-amber-50 text-amber-700",
    red: "bg-red-50 text-red-700",
    blue: "bg-sky-50 text-sky-700",
    lime: "bg-lime-300/40 text-ink-800",
  };
  return (
    <div className={cn("surface p-5", className)}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.08em] text-ink-400">{label}</p>
          <p className="mt-2 font-display text-2xl font-bold tracking-tight text-ink-950">{value}</p>
          {hint && <p className="mt-1.5 text-xs text-ink-400">{hint}</p>}
        </div>
        {Icon && (
          <span className={cn("grid h-10 w-10 place-items-center rounded-xl", tones[tone])}>
            <Icon className="h-5 w-5" />
          </span>
        )}
      </div>
    </div>
  );
}

export function Modal({ open, onClose, title, description, children, footer, size = "md", wide = false }) {
  const panelRef = useRef(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    if (!open) return undefined;
    const previouslyFocused = document.activeElement;
    const panel = panelRef.current;
    const focusableSelector = 'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
    const onKey = (event) => {
      if (event.key === "Escape") {
        onClose?.();
        return;
      }
      if (event.key !== "Tab" || !panel) return;
      const focusable = Array.from(panel.querySelectorAll(focusableSelector)).filter((element) => element.offsetParent !== null);
      if (!focusable.length) {
        event.preventDefault();
        panel.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.requestAnimationFrame(() => panel?.focus());
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
      if (previouslyFocused instanceof HTMLElement) previouslyFocused.focus();
    };
  }, [open, onClose]);

  if (!open) return null;
  const sizes = { sm: "max-w-md", md: "max-w-xl", lg: "max-w-3xl", xl: "max-w-5xl" };
  const sizeClass = wide ? "max-w-5xl" : sizes[size];
  return (
    <div className="fixed inset-0 z-[90] flex items-end justify-center bg-ink-950/55 p-0 backdrop-blur-sm sm:items-center sm:p-6" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
        className={cn("max-h-[92vh] w-full overflow-y-auto rounded-t-3xl bg-white shadow-soft outline-none sm:rounded-3xl", sizeClass)}
      >
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-ink-100 bg-white/95 px-5 py-4 backdrop-blur sm:px-6">
          <div>
            <h2 id={titleId} className="font-display text-lg font-bold text-ink-950">{title}</h2>
            {description && <p id={descriptionId} className="mt-1 text-sm text-ink-500">{description}</p>}
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-ink-400 hover:bg-ink-100 hover:text-ink-700" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="px-5 py-5 sm:px-6">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-ink-100 px-5 py-4 sm:px-6">{footer}</div>}
      </div>
    </div>
  );
}

export function EmptyState({ icon: Icon = Inbox, title, description, action, className }) {
  return (
    <div className={cn("flex flex-col items-center justify-center rounded-2xl border border-dashed border-ink-200 bg-ink-50/50 px-6 py-12 text-center", className)}>
      <span className="grid h-12 w-12 place-items-center rounded-2xl bg-white text-ink-400 shadow-sm">
        <Icon className="h-6 w-6" />
      </span>
      <h3 className="mt-4 font-display text-base font-bold text-ink-900">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm leading-relaxed text-ink-500">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Alert({ tone = "error", title, children, className }) {
  const tones = {
    error: "border-red-200 bg-red-50 text-red-800",
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
    info: "border-sky-200 bg-sky-50 text-sky-800",
    warning: "border-amber-200 bg-amber-50 text-amber-800",
  };
  const Icon = tone === "success" ? CheckCircle2 : AlertCircle;
  return (
    <div className={cn("flex items-start gap-2.5 rounded-xl border p-3.5 text-sm", tones[tone], className)}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div>
        {title && <p className="font-semibold">{title}</p>}
        <div className="leading-relaxed">{children}</div>
      </div>
    </div>
  );
}

export function Tabs({ tabs, active, onChange, className }) {
  return (
    <div role="tablist" className={cn("no-scrollbar flex gap-1 overflow-x-auto rounded-xl bg-ink-100/70 p-1", className)}>
      {tabs.map((tab) => (
        <button
          key={tab.value}
          type="button"
          role="tab"
          aria-selected={active === tab.value}
          onClick={() => onChange(tab.value)}
          className={cn(
            "whitespace-nowrap rounded-lg px-3.5 py-2 text-xs font-semibold transition",
            active === tab.value ? "bg-white text-ink-950 shadow-sm" : "text-ink-500 hover:text-ink-800"
          )}
        >
          {tab.label}
          {tab.count !== undefined && <span className="ml-1.5 text-ink-400">{tab.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Pagination({ page, count, pageSize = 25, onPage }) {
  const pages = Math.max(1, Math.ceil(count / pageSize));
  if (pages <= 1) return null;
  return (
    <div className="mt-4 flex items-center justify-between gap-3 text-sm text-ink-500">
      <span>
        Page {page} of {pages} · {count} records
      </span>
      <div className="flex gap-2">
        <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)} icon={ChevronLeft}>
          Previous
        </Button>
        <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

export function SectionTitle({ title, description, action, className }) {
  return (
    <div className={cn("mb-4 flex flex-wrap items-end justify-between gap-3", className)}>
      <div>
        <h2 className="font-display text-lg font-bold text-ink-950">{title}</h2>
        {description && <p className="mt-1 text-sm text-ink-500">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function SkeletonRows({ rows = 4, className }) {
  return (
    <div className={cn("space-y-2", className)}>
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="skeleton h-14 w-full" />
      ))}
    </div>
  );
}
