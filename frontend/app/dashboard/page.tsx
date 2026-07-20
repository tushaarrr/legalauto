"use client";

import { useEffect, useState } from "react";
import { fetchStats } from "@/lib/api";
import type { Stats } from "@/lib/types";
import {
  BarList,
  Card,
  EmptyState,
  StatTile,
  StatusPill,
  type BarDatum,
} from "@/components/charts";
import {
  AlertTriangle,
  Inbox,
  OctagonAlert,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "@/components/icons";

const FIELD_LABELS: Record<string, string> = {
  opposing_party: "Opposing party",
  client_phone: "Phone",
  client_email: "Email",
  client_name: "Client name",
  jurisdiction: "Jurisdiction",
  key_dates: "Key dates",
};

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load stats."));
  }, []);

  if (error) {
    return (
      <Shell>
        <Card>
          <EmptyState>
            {error}. Is the backend running on the port in NEXT_PUBLIC_API_BASE_URL?
          </EmptyState>
        </Card>
      </Shell>
    );
  }

  if (!stats) {
    // Skeleton rather than a spinner — reserves the layout so nothing shifts in.
    return (
      <Shell>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-28 animate-pulse rounded-xl border border-line bg-surface-2" />
          ))}
        </div>
      </Shell>
    );
  }

  if (stats.empty) {
    return (
      <Shell>
        <Card title="No approved intakes yet">
          <EmptyState>
            Process and approve an intake on the Review page and it will appear here.
          </EmptyState>
        </Card>
      </Shell>
    );
  }

  const flagged = stats.conflict.CONFLICT + stats.conflict.POTENTIAL;

  // Status rows: colour is reinforcement only — each carries an icon and label.
  const conflictBars: BarDatum[] = [
    {
      label: "Conflict",
      value: stats.conflict.CONFLICT,
      color: "var(--crit)",
      icon: <OctagonAlert className="h-3.5 w-3.5 text-crit" />,
    },
    {
      label: "Potential",
      value: stats.conflict.POTENTIAL,
      color: "var(--warn)",
      icon: <ShieldAlert className="h-3.5 w-3.5 text-warn" />,
    },
    {
      label: "Clear",
      value: stats.conflict.CLEAR,
      color: "var(--good)",
      icon: <ShieldCheck className="h-3.5 w-3.5 text-good" />,
    },
  ];

  const matterBars: BarDatum[] = stats.matter_types.map((m) => ({
    label: m.name,
    value: m.count,
  }));

  const missingBars: BarDatum[] = stats.missing_fields.map((m) => ({
    label: FIELD_LABELS[m.field] ?? m.field,
    value: m.count,
  }));

  const topMissing = stats.missing_fields[0];
  const incompletePct = Math.round((stats.incomplete_screens / stats.total_intakes) * 100);

  return (
    <Shell>
      {/* KPI row — the four numbers a firm would actually act on. */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Intakes processed"
          value={stats.total_intakes}
          hint="Approved by a human and written to the CRM"
          icon={<Inbox className="h-3.5 w-3.5" />}
        />
        <StatTile
          label="Conflict exposure"
          value={stats.conflict_rate_pct}
          unit="%"
          tone={flagged > 0 ? "warn" : "good"}
          hint={`${flagged} of ${stats.total_intakes} matched a party in ${stats.history_size} past matters`}
          icon={<ShieldAlert className="h-3.5 w-3.5" />}
        />
        <StatTile
          label="Incomplete screens"
          value={stats.incomplete_screens}
          tone={stats.incomplete_screens > 0 ? "warn" : "good"}
          hint="Only one side could be screened — no opposing party named"
          icon={<AlertTriangle className="h-3.5 w-3.5" />}
        />
        <StatTile
          label="Needed a second look"
          value={stats.low_confidence_pct ?? 0}
          unit="%"
          hint={`${stats.confidence.low} classified with low confidence`}
          icon={<Sparkles className="h-3.5 w-3.5" />}
        />
      </div>

      {/*
        The insight, stated in words. A dashboard that only draws bars makes the
        reader derive the finding; this names it and says what to do about it.
      */}
      {topMissing && (
        <div className="mt-4 flex items-start gap-3 rounded-xl border border-accent/30 bg-warn-bg p-4">
          <Sparkles className="mt-0.5 h-4 w-4 text-accent" />
          <p className="text-sm leading-relaxed text-ink-primary">
            <span className="font-semibold">What to fix first: </span>
            {FIELD_LABELS[topMissing.field] ?? topMissing.field} was missing from{" "}
            <span className="tnum font-semibold">{topMissing.count}</span> of{" "}
            <span className="tnum font-semibold">{stats.total_intakes}</span> intakes
            {topMissing.field === "opposing_party" && (
              <>
                , which is why {incompletePct}% of conflict screens could only check one
                side
              </>
            )}
            . Adding it to your intake form removes that gap at the source.
          </p>
        </div>
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card
          title="Conflict screen outcomes"
          subtitle={`Every intake checked against ${stats.history_size} past matters`}
        >
          <BarList data={conflictBars} total={stats.total_intakes} />
        </Card>

        <Card
          title="Missing information by field"
          subtitle="What clients most often leave out — each one is a follow-up email"
        >
          <BarList
            data={missingBars}
            total={stats.total_intakes}
            emptyMessage="No missing fields recorded."
          />
        </Card>

        <Card title="Matter types" subtitle="Distribution across approved intakes">
          <BarList data={matterBars} total={stats.total_intakes} />
        </Card>

        <Card title="Recent intakes" subtitle="Most recently approved first">
          {stats.recent.length === 0 ? (
            <EmptyState>Nothing approved yet.</EmptyState>
          ) : (
            <div className="-mx-2 overflow-x-auto">
              <table className="w-full min-w-[420px] text-sm">
                <caption className="sr-only">
                  Recently approved intakes with matter type and conflict result
                </caption>
                <thead>
                  <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
                    <th scope="col" className="px-2 pb-2 font-medium">Client</th>
                    <th scope="col" className="px-2 pb-2 font-medium">Matter</th>
                    <th scope="col" className="px-2 pb-2 font-medium">Conflict</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.recent.map((r) => (
                    <tr
                      key={r.intake_id}
                      className="border-b border-line/60 transition-colors duration-150 last:border-0 hover:bg-surface-2"
                    >
                      <td className="px-2 py-2">
                        <span className="block text-ink-primary">{r.client_name}</span>
                        <span className="tnum text-xs text-ink-muted">{r.intake_id}</span>
                      </td>
                      <td className="px-2 py-2 text-ink-secondary">{r.matter_type}</td>
                      <td className="px-2 py-2">
                        <StatusPill status={r.conflict_status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      <div className="mb-5">
        <h1 className="font-display text-[26px] font-bold tracking-tight text-heading">
          Intake analytics
        </h1>
        <p className="mt-1 text-sm text-ink-secondary">
          Derived only from intakes a human reviewed and approved. Nothing here is
          estimated.
        </p>
      </div>
      {children}
    </div>
  );
}
