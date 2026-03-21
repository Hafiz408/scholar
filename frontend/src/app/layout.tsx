import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

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
    <html lang="en">
      <body className="flex h-screen overflow-hidden bg-gray-50">
        <nav className="w-48 flex-shrink-0 bg-gray-900 text-white flex flex-col p-4 gap-1">
          <div className="text-lg font-bold mb-4 text-white">Scholar</div>
          <Link
            href="/knowledge"
            className="px-3 py-2 rounded text-gray-300 hover:bg-gray-700 hover:text-white transition-colors text-sm"
          >
            Knowledge
          </Link>
          <Link
            href="/goals/new"
            className="px-3 py-2 rounded text-gray-300 hover:bg-gray-700 hover:text-white transition-colors text-sm"
          >
            New Goal
          </Link>
          <Link
            href="/super"
            className="px-3 py-2 rounded text-gray-300 hover:bg-gray-700 hover:text-white transition-colors text-sm"
          >
            Super Agent
          </Link>
        </nav>
        <main className="flex-1 overflow-auto h-full">
          {children}
        </main>
      </body>
    </html>
  );
}
