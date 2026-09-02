import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";
import { Suspense } from "react";

import { LoginCard } from "@/components/features/auth/LoginCard";
import { DotGrid } from "@/components/layout/DotGrid";
import { authOptions } from "@/lib/auth";

export default async function LoginPage() {
  const session = await getServerSession(authOptions);
  if (session?.memoriaToken) {
    redirect("/dashboard");
  }

  return (
    <main className="relative flex min-h-full flex-1 items-center justify-center px-6 py-16">
      <DotGrid />
      <div className="relative flex w-full max-w-md flex-col items-center">
        <p className="mb-8 font-mono text-sm tracking-[0.2em]">MEMORIA</p>
        <Suspense>
          <LoginCard />
        </Suspense>
      </div>
    </main>
  );
}
