import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "KAVAL-X | Advanced Fraud Detection & Banking Security",
  description: "Multi-model fraud detection system combining TGN graph neural networks, PINN biometrics, APK analysis, and adversarial debate protocols for real-time banking security.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased bg-kx-bg text-kx-head min-h-screen flex">
        <Sidebar />
        <div className="flex-1 flex flex-col min-h-screen ml-[72px]">
          {/* Top Header */}
          <header className="h-14 border-b border-kx-border bg-kx-surface/80 backdrop-blur-md flex items-center px-6 gap-4 shrink-0 z-10">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center font-black text-sm text-kx-bg"
              style={{ background: 'linear-gradient(135deg, #00FFD1, #7B61FF)' }}>
              K
            </div>
            <div>
              <div className="text-sm font-extrabold tracking-tight">
                KAVAL-X <span className="text-kx-teal">Fraud Detection</span>
              </div>
              <div className="text-[10px] text-kx-muted tracking-[1.5px]">
                ADVANCED FRAUD DETECTION &amp; BANKING SECURITY
              </div>
            </div>
            <div className="ml-auto flex items-center gap-3">
              <div className="flex gap-1.5">
                {['#00FFD1','#7B61FF','#FF6B35','#FFD700','#FF3CAC'].map((c,i) => (
                  <div key={i} className="w-1.5 h-1.5 rounded-full" style={{background:c}} />
                ))}
              </div>
              <div className="flex items-center gap-2 text-xs text-kx-muted">
                <div className="w-2 h-2 rounded-full bg-green-400 pulse-dot" />
                LIVE
              </div>
            </div>
          </header>
          {/* Main Content */}
          <main className="flex-1 overflow-auto p-6">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
