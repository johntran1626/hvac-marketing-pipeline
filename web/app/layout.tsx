import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Wren Air & Heat",
  description: "Marketing pipeline and dashboard for Wren Air & Heat",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
