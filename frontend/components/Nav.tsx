"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, FileSearch, Scale, Search } from "./icons";
import { ThemeToggle } from "./ThemeToggle";

const links = [
  { href: "/", label: "Review", Icon: FileSearch },
  { href: "/dashboard", label: "Dashboard", Icon: LayoutDashboard },
];

/** Full-width product bar: solid brand blue, white controls. */
export function AppBar() {
  return (
    <header className="sticky top-0 z-40 bg-appbar">
      <div className="flex h-14 items-center gap-3 px-3 sm:px-4">
        <Link href="/" className="flex items-center gap-2 text-white">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/15">
            <Scale className="h-[18px] w-[18px]" />
          </span>
          <span className="text-base font-semibold tracking-tight">LegalFlow</span>
        </Link>

        {/* Presentational search field — matches the product bar it mirrors. */}
        <div className="relative ml-2 hidden max-w-md flex-1 md:block">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-white/70" />
          <input
            type="search"
            aria-label="Search intakes"
            placeholder="Search intakes"
            className="h-9 w-full rounded-md border border-white/25 bg-white/15 pl-8 pr-3 text-sm text-white placeholder:text-white/70"
          />
        </div>

        <div className="ml-auto flex items-center gap-2">
          <span className="hidden text-xs text-white/85 lg:inline">
            Synthetic data · no legal advice · nothing auto-sent
          </span>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

/**
 * Fixed navy icon rail. Hidden below `sm`, where the horizontal strip under the
 * app bar takes over — an icon-only rail is too cramped to label at 375px.
 */
export function SideRail() {
  const pathname = usePathname();

  return (
      <nav
        aria-label="Main"
        className="fixed bottom-0 left-0 top-14 z-30 hidden w-16 flex-col items-center gap-1 border-r border-black/20 bg-rail py-3 sm:flex"
      >
        {links.map(({ href, label, Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              title={label}
              // Active state is a filled tile + white ink, not colour alone.
              className={`relative flex h-11 w-11 flex-col items-center justify-center rounded-lg transition-colors duration-200 ${
                active
                  ? "text-rail-ink-active"
                  : "text-rail-ink hover:bg-rail-2 hover:text-rail-ink-active"
              }`}
            >
              {/* One element shared across items, so the highlight slides
                  between them instead of blinking out and in. */}
              {active && (
                <motion.span
                  layoutId="rail-active"
                  className="absolute inset-0 rounded-lg bg-brand"
                  transition={{ type: "spring", stiffness: 450, damping: 35 }}
                />
              )}
              <Icon className="relative h-5 w-5" />
              <span className="sr-only">{label}</span>
            </Link>
          );
        })}
      </nav>
  );
}

/**
 * Small screens get a labelled horizontal nav instead of the icon rail — an
 * icon-only rail is too cramped to label at 375px.
 *
 * Kept OUT of any flex row with <main>: as a full-width flex sibling it would
 * occupy a whole column and push the content off-screen rather than sitting
 * above it.
 */
export function MobileNav() {
  const pathname = usePathname();

  return (
      <nav
        aria-label="Main"
        className="sticky top-14 z-30 flex w-full gap-1 border-b border-line bg-surface px-3 py-2 sm:hidden"
      >
        {links.map(({ href, label, Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={`relative inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm transition-colors duration-200 ${
                active ? "font-semibold text-brand" : "font-medium text-ink-secondary"
              }`}
            >
              {active && (
                <motion.span
                  layoutId="mobile-active"
                  className="absolute inset-0 rounded-lg bg-surface-3"
                  transition={{ type: "spring", stiffness: 450, damping: 35 }}
                />
              )}
              <Icon className="relative h-4 w-4" />
              <span className="relative">{label}</span>
            </Link>
          );
        })}
      </nav>
  );
}
