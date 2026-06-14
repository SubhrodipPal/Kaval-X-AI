"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, GitBranch, Swords, Smartphone, ClipboardList, Eye, Settings } from "lucide-react";

const NAV = [
  { href: "/", icon: BarChart3, label: "Dashboard", color: "#00FFD1" },
  { href: "/graph", icon: GitBranch, label: "Graph", color: "#7B61FF" },
  { href: "/amadp", icon: Swords, label: "AMADP", color: "#FF3CAC" },
  { href: "/biometrics", icon: Smartphone, label: "Biometrics", color: "#FFD700" },
  { href: "/compliance", icon: ClipboardList, label: "Compliance", color: "#FF6B35" },
  { href: "/osint", icon: Eye, label: "OSINT", color: "#00C9FF" },
  { href: "/settings", icon: Settings, label: "Settings", color: "#4A6880" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <nav className="fixed left-0 top-0 h-screen w-[72px] bg-kx-surface border-r border-kx-border flex flex-col items-center py-4 gap-1 z-20">
      {/* Logo */}
      <div className="w-10 h-10 rounded-xl flex items-center justify-center font-black text-lg text-kx-bg mb-6"
        style={{ background: 'linear-gradient(135deg, #00FFD1, #7B61FF)' }}>
        K
      </div>

      {NAV.map(({ href, icon: Icon, label, color }) => {
        const active = pathname === href || (href !== "/" && pathname.startsWith(href));
        return (
          <Link
            key={href}
            href={href}
            title={label}
            className="group relative w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-200"
            style={{
              background: active ? `${color}15` : 'transparent',
              borderLeft: active ? `3px solid ${color}` : '3px solid transparent',
            }}
          >
            <Icon
              size={20}
              style={{ color: active ? color : '#4A6880' }}
              className="transition-colors duration-200 group-hover:scale-110"
            />
            {/* Tooltip */}
            <span className="absolute left-16 px-2 py-1 rounded-md text-xs font-semibold bg-kx-surface border border-kx-border text-kx-head opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
              {label}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
