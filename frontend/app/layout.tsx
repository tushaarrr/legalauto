import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LegalFlow — Intake Review",
  description:
    "Approval-first client intake automation. Synthetic data, no legal advice, nothing auto-sent.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
