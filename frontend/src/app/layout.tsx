import "./globals.css";
import Navigation from "@/components/Navigation";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "RELAY // Self-Learning LLM Router",
  description: "Bayesian Thompson Sampling Router across Gemini Tiers - Brutalist Pop Edition",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-[#FFE14D] text-black font-mono min-h-screen flex flex-col selection:bg-[#FF4FA3] selection:text-black">
        <Navigation />
        <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
          {children}
        </main>
        <footer className="border-t-[3px] border-black bg-[#FFE14D] py-4 text-center">
          <p className="font-mono font-bold text-xs sm:text-sm tracking-wider uppercase text-black">
            RELAY // routes prompts, learns from thumbs
          </p>
        </footer>
      </body>
    </html>
  );
}
