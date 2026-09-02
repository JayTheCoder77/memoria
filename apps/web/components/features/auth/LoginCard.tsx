"use client";

import { signIn } from "next-auth/react";
import { useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { StatusPill } from "@/components/ui/StatusPill";

export function LoginCard() {
  const params = useSearchParams();
  const error = params.get("error");
  const loading = params.get("callback") === "1";

  return (
    <Card className="w-full max-w-md p-8">
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-text-secondary">
        Sign in
      </p>
      <h1 className="mt-3 text-2xl font-semibold">Access your memory dashboard</h1>
      {loading ? (
        <p className="mt-8 font-mono text-sm text-text-secondary">&gt; Authenticating...</p>
      ) : (
        <Button
          className="mt-8 w-full"
          variant="google"
          onClick={() => signIn("google", { callbackUrl: "/dashboard" })}
        >
          Sign in with Google
        </Button>
      )}
      {error ? (
        <p className="mt-4 text-sm text-danger">
          Google sign-in failed. Check AUTH_GOOGLE_ID and AUTH_GOOGLE_SECRET, then retry.
        </p>
      ) : (
        <div className="mt-4">
          <StatusPill status="secure" />
        </div>
      )}
      <p className="mt-8 text-xs text-text-secondary">
        By continuing you agree to the product Terms and Privacy notice.
      </p>
    </Card>
  );
}
