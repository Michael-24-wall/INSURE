import { cn } from "./ui";

const OVERLAYS = {
  blue: "bg-gradient-to-r from-ink-950/90 via-ink-950/60 to-ink-950/25",
  blueUp: "bg-gradient-to-t from-ink-950/85 via-ink-950/40 to-ink-950/10",
  dark: "bg-gradient-to-r from-ink-950/80 via-ink-950/40 to-transparent",
};

export function ImageOverlay({ tone = "blue", className }) {
  return <div aria-hidden className={cn("pointer-events-none absolute inset-0", OVERLAYS[tone] || OVERLAYS.blue, className)} />;
}

export function HeroSection({ image, alt = "", tone = "blue", eyebrow, title, text, children, className, height = "min-h-[560px]" }) {
  return (
    <section className={cn("relative isolate overflow-hidden bg-ink-950", className)}>
      <img src={image} alt={alt} className="absolute inset-0 h-full w-full object-cover" loading="eager" />
      <ImageOverlay tone={tone} />
      <div className={cn("relative mx-auto flex max-w-7xl flex-col justify-center px-4 py-16 sm:px-6 lg:px-8 lg:py-20", height)}>
        {eyebrow && <p className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.14em] text-white/80 backdrop-blur">{eyebrow}</p>}
        {title && <h1 className="mt-5 max-w-2xl font-display text-4xl font-bold leading-[1.05] tracking-[-0.03em] text-white sm:text-5xl lg:text-6xl">{title}</h1>}
        {text && <p className="mt-5 max-w-xl text-base leading-relaxed text-white/70 sm:text-lg">{text}</p>}
        {children}
      </div>
    </section>
  );
}

export function SplashBanner({ image, alt = "", eyebrow, title, text, children, className }) {
  return (
    <section className={cn("relative isolate overflow-hidden", className)}>
      <img src={image} alt={alt} className="absolute inset-0 h-full w-full object-cover" loading="lazy" />
      <ImageOverlay tone="blue" />
      <div className="relative mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8 lg:py-20">
        {eyebrow && <p className="eyebrow !text-brand-300">{eyebrow}</p>}
        {title && <h2 className="mt-3 max-w-2xl font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">{title}</h2>}
        {text && <p className="mt-3 max-w-xl text-base leading-relaxed text-white/70">{text}</p>}
        {children}
      </div>
    </section>
  );
}

export function SectionBanner({ image, alt = "", eyebrow, title, text, actions, className }) {
  return (
    <section className={cn("relative isolate overflow-hidden rounded-3xl", className)}>
      <img src={image} alt={alt} className="absolute inset-0 h-full w-full object-cover" loading="lazy" />
      <ImageOverlay tone="blue" />
      <div className="relative flex flex-col gap-4 px-6 py-10 sm:flex-row sm:items-center sm:justify-between sm:px-10 sm:py-14">
        <div>
          {eyebrow && <p className="eyebrow !text-brand-300">{eyebrow}</p>}
          {title && <h2 className="mt-2 max-w-xl font-display text-2xl font-bold tracking-tight text-white sm:text-3xl">{title}</h2>}
          {text && <p className="mt-2 max-w-lg text-sm leading-relaxed text-white/70">{text}</p>}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
    </section>
  );
}

export function DashboardHero({ image, alt = "", eyebrow, title, text, actions, className }) {
  return (
    <section className={cn("relative isolate mb-6 overflow-hidden rounded-3xl", className)}>
      <img src={image} alt={alt} className="absolute inset-0 h-full w-full object-cover" loading="lazy" />
      <ImageOverlay tone="dark" />
      <div className="relative flex flex-col gap-4 px-6 py-8 sm:flex-row sm:items-center sm:justify-between sm:px-8 sm:py-9">
        <div>
          {eyebrow && <p className="eyebrow !text-brand-300">{eyebrow}</p>}
          {title && <h1 className="mt-1.5 max-w-2xl font-display text-xl font-bold tracking-tight text-white sm:text-2xl">{title}</h1>}
          {text && <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-white/70">{text}</p>}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
    </section>
  );
}
