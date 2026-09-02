import { Button } from "@/components/ui/Button";
import { DotGrid } from "@/components/layout/DotGrid";

export function FinalCta() {
  return (
    <section className="relative overflow-hidden border-t border-border-subtle px-6 py-24 text-center md:px-10">
      <DotGrid />
      <div className="relative mx-auto max-w-2xl">
        <h2 className="text-4xl font-semibold md:text-5xl">Give your agent a memory.</h2>
        <p className="mt-4 text-sm text-text-secondary">No credit card required.</p>
        <div className="mt-8 flex justify-center">
          <Button href="/login">Get API Key</Button>
        </div>
      </div>
    </section>
  );
}
