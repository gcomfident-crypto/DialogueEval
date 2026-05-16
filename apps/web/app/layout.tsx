import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DialogueEval",
  description: "Instruction-following evaluation system for outbound dialogue models",
  icons: {
    icon: "/logo-mark.svg"
  }
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
