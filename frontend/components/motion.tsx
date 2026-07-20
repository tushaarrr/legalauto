"use client";

import {
  MotionConfig,
  animate,
  useInView,
  useMotionValue,
  useReducedMotion,
  type Variants,
} from "framer-motion";
import { useEffect, useRef, useState } from "react";

/*
  Motion vocabulary for the app, in one place so everything shares a rhythm.

  The rules these follow:
  - Micro-interactions 150-300ms; nothing decorative runs past 400ms.
  - Only transform and opacity animate. Width/height/top/left cause layout work
    on every frame; the bars below scale on the X axis instead.
  - Enter with ease-out, exit faster than enter (~65%), so the UI feels
    responsive rather than draggy.
  - Motion expresses cause and effect. Cards rise as they arrive, the conflict
    banner springs in because it is an alert, numbers count because they are
    counts. Nothing moves purely to be seen moving.
  - reducedMotion="user" is set once on the provider, so every animation here
    collapses to an instant state change when the OS asks for that.
*/

export function MotionProvider({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}

/** Container that staggers its children in. */
export const stagger: Variants = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.05, delayChildren: 0.04 },
  },
};

/** Standard card/section entrance: a short rise with a fade. */
export const riseIn: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.32, ease: [0.16, 1, 0.3, 1] },
  },
  exit: {
    opacity: 0,
    y: -6,
    transition: { duration: 0.2, ease: [0.4, 0, 1, 1] },
  },
};

/** For content that replaces other content in the same box. */
export const crossFade: Variants = {
  hidden: { opacity: 0, scale: 0.98 },
  show: {
    opacity: 1,
    scale: 1,
    transition: { type: "spring", stiffness: 380, damping: 30 },
  },
  exit: { opacity: 0, scale: 0.98, transition: { duration: 0.18 } },
};

/**
 * The conflict banner. A spring rather than a tween: this is the one moment in
 * the app where something genuinely demands attention, and the slight overshoot
 * reads as "this arrived" instead of "this faded in".
 */
export const alertIn: Variants = {
  hidden: { opacity: 0, y: -8, scale: 0.985 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { type: "spring", stiffness: 420, damping: 26 },
  },
  exit: { opacity: 0, scale: 0.99, transition: { duration: 0.16 } },
};

/** Press feedback for buttons — subtle, and it never shifts layout. */
export const pressable = {
  whileHover: { scale: 1.01 },
  whileTap: { scale: 0.985 },
  transition: { type: "spring" as const, stiffness: 600, damping: 30 },
};

/**
 * Counts a number up when it scrolls into view.
 *
 * Reads as the value being tallied rather than asserted. Falls straight to the
 * final value under reduced motion — the number is the point, the animation is
 * not.
 */
export function CountUp({
  value,
  decimals = 0,
  duration = 0.9,
}: {
  value: number;
  decimals?: number;
  duration?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const reduced = useReducedMotion();
  const mv = useMotionValue(0);
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (!inView) return;
    if (reduced) {
      setShown(value);
      return;
    }
    const controls = animate(mv, value, {
      duration,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => setShown(v),
    });
    return () => controls.stop();
  }, [inView, value, duration, reduced, mv]);

  return <span ref={ref}>{shown.toFixed(decimals)}</span>;
}
