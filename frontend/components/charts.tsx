import type { ReactNode } from "react";

/*
  Chart primitives, built in plain HTML/CSS — no chart library.

  Decisions worth defending:
  - Horizontal bars, not vertical: every category here has a text label, and
    horizontal rows let labels read left-to-right at any length without rotation.
  - Values are DIRECT-LABELLED on every row rather than hidden behind a hover
    tooltip, so the numbers survive touch, print, and screen readers.
  - Single-measure bars use ONE hue. Colouring each bar differently would imply
    the colour encodes something; it doesn't — the row label carries identity.
  - Every chart has an explicit empty state. A zeroed axis is not an empty state.
*/

export function Card({
  title,
  subtitle,
  children,
  className = "",
  action,
}: {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
  action?: ReactNode;
}) {
  return (
    <section
      // min-w-0 matters: as a grid child this would otherwise default to
      // min-width:auto and let wide content (the data table) push the whole
      // page wider than the viewport instead of scrolling inside its own box.
      className={`min-w-0 rounded-xl border border-line bg-surface p-5 shadow-card ${className}`}
    >
      {(title || action) && (
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            {title && (
              <h2 className="font-display text-[15px] font-bold tracking-tight text-heading">
                {title}
              </h2>
            )}
            {subtitle && (
              <p className="mt-0.5 text-xs leading-relaxed text-ink-muted">{subtitle}</p>
            )}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-line-strong px-4 py-6 text-center text-sm text-ink-muted">
      {children}
    </p>
  );
}

/** A headline number. No plot, so no tooltip — the value is the whole point. */
export function StatTile({
  label,
  value,
  unit,
  hint,
  tone = "neutral",
  icon,
}: {
  label: string;
  value: string | number;
  unit?: string;
  hint?: string;
  tone?: "neutral" | "good" | "warn" | "crit";
  icon?: ReactNode;
}) {
  const toneClass = {
    neutral: "text-ink-primary",
    good: "text-good",
    warn: "text-warn",
    crit: "text-crit",
  }[tone];

  return (
    <div className="rounded-xl border border-line bg-surface p-4 shadow-card">
      <div className="flex items-center gap-2 text-ink-secondary">
        {icon}
        <span className="text-xs font-medium uppercase tracking-wide">{label}</span>
      </div>
      <p className={`tnum mt-2 font-display text-[30px] font-bold leading-none ${toneClass}`}>
        {value}
        {unit && <span className="ml-1 text-lg font-normal text-ink-muted">{unit}</span>}
      </p>
      {hint && <p className="mt-2 text-xs leading-relaxed text-ink-muted">{hint}</p>}
    </div>
  );
}

export type BarDatum = {
  label: string;
  value: number;
  /** Optional per-row colour. Used only where a STATUS meaning exists. */
  color?: string;
  icon?: ReactNode;
  note?: string;
};

/**
 * Horizontal bar list for magnitude comparison.
 *
 * `color` is only passed by the conflict breakdown, where each row is a status
 * and ships an icon plus its text label — so colour reinforces meaning that is
 * already carried in two other channels, never replaces it.
 */
export function BarList({
  data,
  total,
  emptyMessage = "No data yet.",
  valueSuffix = "",
}: {
  data: BarDatum[];
  total?: number;
  emptyMessage?: string;
  valueSuffix?: string;
}) {
  if (!data.length) return <EmptyState>{emptyMessage}</EmptyState>;

  const max = Math.max(total ?? 0, ...data.map((d) => d.value), 1);

  return (
    <ul className="space-y-2.5">
      {data.map((d, i) => {
        const pct = (d.value / max) * 100;
        const share = total ? Math.round((d.value / total) * 100) : null;
        return (
          <li
            key={d.label}
            className="group -mx-2 rounded-lg px-2 py-1 transition-colors duration-150 hover:bg-surface-2"
            title={`${d.label}: ${d.value}${valueSuffix}${share !== null ? ` (${share}%)` : ""}`}
          >
            <div className="mb-1 flex items-baseline justify-between gap-3">
              <span className="flex items-center gap-1.5 text-sm text-ink-primary">
                {d.icon}
                {d.label}
              </span>
              <span className="tnum text-sm font-semibold text-ink-primary">
                {d.value}
                {valueSuffix}
                {share !== null && (
                  <span className="ml-1.5 text-xs font-normal text-ink-muted">{share}%</span>
                )}
              </span>
            </div>
            {/* Track is recessive so it never competes with the data. */}
            <div className="h-2 w-full overflow-hidden rounded-full bg-chart-track">
              <div
                className="bar-grow h-full rounded-full"
                style={{
                  width: `${Math.max(pct, d.value > 0 ? 2 : 0)}%`,
                  backgroundColor: d.color ?? "var(--chart-bar)",
                  animationDelay: `${i * 40}ms`,
                }}
              />
            </div>
            {d.note && <p className="mt-1 text-xs text-ink-muted">{d.note}</p>}
          </li>
        );
      })}
    </ul>
  );
}

/** Status pill — always icon + text, never colour alone. */
export function StatusPill({
  status,
}: {
  status: "CLEAR" | "POTENTIAL" | "CONFLICT" | "NOT_CHECKED";
}) {
  const map = {
    CONFLICT: { label: "Conflict", cls: "bg-crit-bg text-crit border-crit/30" },
    POTENTIAL: { label: "Potential", cls: "bg-warn-bg text-warn border-warn/30" },
    CLEAR: { label: "Clear", cls: "bg-good-bg text-good border-good/30" },
    NOT_CHECKED: {
      label: "Not checked",
      cls: "bg-surface-2 text-ink-muted border-line-strong",
    },
  }[status];

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${map.cls}`}
    >
      {map.label}
    </span>
  );
}
