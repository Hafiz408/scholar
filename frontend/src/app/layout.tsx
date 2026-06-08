import type { Metadata } from "next";
import { Inter, Fraunces } from "next/font/google";
import Nav from "@/components/ui/Nav";
import "./globals.css";

// Body / UI — clean, neutral sans.
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

// Headings / display — characterful scholarly serif.
const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-serif",
  display: "swap",
  axes: ["opsz"],
});

export const metadata: Metadata = {
  title: "Scholar",
  description: "Your AI-powered study companion",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${fraunces.variable}`}>
      <body className="flex h-screen overflow-hidden bg-surface font-sans text-ink-soft antialiased">
        <Nav />
        <main className="h-full flex-1 overflow-auto">{children}</main>
      </body>
    </html>
  );
}
