import { Card } from "@/components/ui/Card";
import { SectionLabel } from "@/components/ui/SectionLabel";

export default function PricingPage() {
  return (
    <section className="mx-auto max-w-4xl px-6 py-20 md:px-10">
      <SectionLabel>Pricing</SectionLabel>
      <h1 className="mt-6 text-4xl font-semibold">Free while we dogfood.</h1>
      <p className="mt-4 max-w-xl text-text-secondary">
        No credit card. Generate a key, point MCP at the API, and start recalling.
      </p>
      <div className="mt-12 grid gap-6 md:grid-cols-2">
        <Card className="p-6">
          <p className="font-mono text-xs text-accent">01</p>
          <h2 className="mt-3 text-xl font-semibold">Hosted MVP</h2>
          <p className="mt-3 text-sm leading-6 text-text-secondary">
            Google sign-in, org-scoped keys, extraction worker. Metering comes later.
          </p>
        </Card>
        <Card className="p-6">
          <p className="font-mono text-xs text-accent">02</p>
          <h2 className="mt-3 text-xl font-semibold">Self-host</h2>
          <p className="mt-3 text-sm leading-6 text-text-secondary">
            Same stack on your machine. Docker Postgres, Memory API, MCP server.
          </p>
        </Card>
      </div>
    </section>
  );
}
