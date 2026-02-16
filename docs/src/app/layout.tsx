import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { Header } from "@/components/header";
import { ApiProvider } from "@/components/api-context";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PolicyEngine API v2 | Documentation",
  description: "Interactive API documentation for PolicyEngine's tax-benefit microsimulation API",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} ${jetbrainsMono.variable} antialiased`}>
        <ApiProvider>
          <div className="flex min-h-screen">
            <Sidebar />
            <div className="flex-1 flex flex-col ml-64">
              <Header />
              <main className="flex-1 p-8 bg-[var(--color-surface)]">
                {children}
              </main>
            </div>
          </div>
        </ApiProvider>
      </body>
    </html>
  );
}
