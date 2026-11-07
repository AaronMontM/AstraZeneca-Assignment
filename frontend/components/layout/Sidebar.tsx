"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
  MessageSquare,
  LayoutDashboard,
  FileSpreadsheet,
  History,
  ChevronRight,
} from "lucide-react";

const navigation = [
  {
    name: "AI Assistant",
    description: "Intelligent finance assistant",
    href: "/assistant",
    icon: MessageSquare,
  },
  {
    name: "Dashboard",
    description: "Financial overview",
    href: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    name: "Data Explorer",
    description: "Invoice records",
    href: "/data",
    icon: FileSpreadsheet,
  },
  {
    name: "Recent History",
    description: "Previous conversations",
    href: "/history",
    icon: History,
  },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-gray-200 bg-white">
      {/* Brand */}
      <div className="flex h-20 flex-col justify-center gap-1 border-b border-gray-100 px-6">
        <Image
          src="/images/logo.jpeg"
          alt="AstraZeneca"
          width={150}
          height={60}
          priority
          className="h-10 w-auto max-w-full object-contain object-left"
        />

        <p className="text-[10px] font-medium uppercase tracking-[0.13em] text-gray-400">
          Finance Intelligence
        </p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-2 px-3 py-7">
        <p className="mb-4 px-3 text-[10px] font-semibold uppercase tracking-[0.15em] text-gray-400">
          Workspace
        </p>

        {navigation.map((item) => {
          const isActive =
            pathname === item.href ||
            pathname.startsWith(`${item.href}/`);

          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group relative flex items-center gap-3 rounded-xl px-3 py-3 transition-all duration-200 ${
                isActive
                  ? "bg-az-50 text-az-700"
                  : "text-gray-500 hover:bg-gray-50 hover:text-gray-900"
              }`}
            >
              {isActive && (
                <span className="absolute bottom-2 left-0 top-2 w-1 rounded-r-full bg-az-600" />
              )}

              <Icon
                size={19}
                strokeWidth={isActive ? 2.2 : 1.8}
                className={isActive ? "text-az-600" : "text-gray-400"}
              />

              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold">{item.name}</p>
                <p className="mt-0.5 truncate text-[11px] text-gray-400">
                  {item.description}
                </p>
              </div>

              {isActive && (
                <ChevronRight size={15} className="text-az-500" />
              )}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}