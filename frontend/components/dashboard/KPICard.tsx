import type { LucideIcon } from "lucide-react";

interface KPICardProps {
  title: string;
  value: string;
  description: string;
  icon: LucideIcon;
  iconColor?: "az" | "amber";
}

const iconStyles = {
  az: {
    background: "bg-az-50",
    foreground: "text-az-700",
  },
  amber: {
    background: "bg-amber-50",
    foreground: "text-amber-600",
  },
};

export default function KPICard({
  title,
  value,
  description,
  icon: Icon,
  iconColor = "az",
}: KPICardProps) {
  const colors = iconStyles[iconColor];

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500">{title}</p>
          <p className="mt-2 text-2xl font-semibold tracking-tight text-gray-900">
            {value}
          </p>
          <p className="mt-1 text-xs text-gray-500">{description}</p>
        </div>

        <div className={`rounded-lg p-3 ${colors.background}`}>
          <Icon className={`h-5 w-5 ${colors.foreground}`} />
        </div>
      </div>
    </div>
  );
}