import type { ReactNode } from "react";

import { DocsFrame } from "@/components/layout/DocsFrame";

export default function DocsLayout({ children }: { children: ReactNode }) {
  return <DocsFrame>{children}</DocsFrame>;
}
