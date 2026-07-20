import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AppBar, MobileNav, SideRail } from "@/components/Nav";
import { MotionProvider } from "@/components/motion";

/*
  One grotesque for the whole product, mirroring the UI this theme copies:
  headings are heavy weights of the same face rather than a contrasting serif.
  Self-hosted via next/font, so there's no render-blocking request to Google and
  the fallback metrics are matched to avoid a layout shift on swap.
*/
const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
  display: "swap",
});

export const metadata: Metadata = {
  title: "LegalFlow — Intake Review",
  description:
    "Approval-first client intake automation with conflict screening. Synthetic data, no legal advice, nothing auto-sent.",
};

/*
  Applies the stored theme before first paint. Without this the page paints in
  the OS theme then snaps to the stored one — a visible flash on every load.
*/
const themeScript = `
(function(){try{var t=localStorage.getItem('legalflow-theme');if(t){document.documentElement.setAttribute('data-theme',t);}}catch(e){}})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="font-sans">
        <MotionProvider>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-brand focus:px-4 focus:py-2 focus:text-on-brand"
        >
          Skip to main content
        </a>

        <AppBar />
        <MobileNav />
        <SideRail />

        {/* The rail is position:fixed, so main simply reserves its width at
            >=sm rather than sharing a flex row with it. */}
        <main id="main" className="sm:pl-16">
          {children}
        </main>
        </MotionProvider>
      </body>
    </html>
  );
}
