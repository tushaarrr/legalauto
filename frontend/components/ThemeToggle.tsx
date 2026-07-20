"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "./icons";

type Mode = "light" | "dark";

/*
  Stamps data-theme on <html>, which the token blocks in globals.css treat as
  overriding the OS preference in both directions. The initial value is read
  from the same localStorage key the inline script in layout.tsx uses, so the
  button never disagrees with what is already painted.
*/
export function ThemeToggle() {
  const [mode, setMode] = useState<Mode | null>(null);

  useEffect(() => {
    const stored = document.documentElement.getAttribute("data-theme") as Mode | null;
    if (stored) {
      setMode(stored);
    } else {
      setMode(
        window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light",
      );
    }
  }, []);

  function toggle() {
    const next: Mode = mode === "dark" ? "light" : "dark";
    setMode(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("legalflow-theme", next);
    } catch {
      /* private mode — the toggle still works for this session */
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      // Sits on the brand-blue app bar, so it wears white ink rather than the
      // page's text tokens. 36px box + the bar's padding clears a 44px target.
      className="inline-flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg border border-white/25 text-white transition-colors duration-200 hover:bg-white/15"
      aria-label={mode === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      title={mode === "dark" ? "Switch to light theme" : "Switch to dark theme"}
    >
      {/* Render nothing until mounted so server and client markup agree. */}
      {mode === "dark" ? <Sun /> : mode === "light" ? <Moon /> : <span className="h-4 w-4" />}
    </button>
  );
}
