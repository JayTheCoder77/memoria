"use client";

import { signIn } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function LoginCard() {
  const params = useSearchParams();
  const error = params.get("error");

  return (
    <main className="flex min-h-full flex-1 items-center justify-center px-6">
      <div className="w-full max-w-md rounded-xl border border-[#232326] bg-[#121214] p-8">
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-[#8B8B90]">
          Sign in
        </p>
        <h1 className="mt-3 text-2xl font-semibold text-[#F2F2F0]">
          Access your memory dashboard
        </h1>
        <button
          className="mt-8 flex h-11 w-full items-center justify-center rounded-md bg-white text-sm font-medium text-black"
          type="button"
          onClick={() => signIn("google", { callbackUrl: "/dashboard/keys" })}
        >
          Sign in with Google
        </button>
        {error ? (
          <p className="mt-4 text-sm text-[#FF5C5C]">
            Google sign-in failed. Check AUTH_GOOGLE_ID and AUTH_GOOGLE_SECRET,
            then retry.
          </p>
        ) : (
          <p className="mt-4 font-mono text-xs text-[#8B8B90]">
            ● Secure via Google OAuth
          </p>
        )}
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginCard />
    </Suspense>
  );
}
