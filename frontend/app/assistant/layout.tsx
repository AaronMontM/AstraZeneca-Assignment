import type { ReactNode } from "react";

interface AssistantLayoutProps {
  children: ReactNode;
}

export default function AssistantLayout({
  children,
}: AssistantLayoutProps) {
  return <>{children}</>;
}