import { CapabilitiesGrid } from "@/components/features/marketing/CapabilitiesGrid";
import { Faq } from "@/components/features/marketing/Faq";
import { FinalCta } from "@/components/features/marketing/FinalCta";
import { Hero } from "@/components/features/marketing/Hero";
import { IntegrationsStrip } from "@/components/features/marketing/IntegrationsStrip";
import { ProblemSection } from "@/components/features/marketing/ProblemSection";
import { SolutionSection } from "@/components/features/marketing/SolutionSection";
import { SpeedSection } from "@/components/features/marketing/SpeedSection";

export default function LandingPage() {
  return (
    <>
      <Hero />
      <ProblemSection />
      <SolutionSection />
      <SpeedSection />
      <CapabilitiesGrid />
      <IntegrationsStrip />
      <Faq />
      <FinalCta />
    </>
  );
}
