import { SectionHeading } from "@/components/layouts/page";

export function KeySteps() {
  return (
    <section className="mt-8 max-w-[65ch]">
      <SectionHeading>Create your Personal API key</SectionHeading>
      <ol className="mt-4 grid list-decimal gap-1.5 pl-5">
        <li>
          In Garmin Connect on the web, open <strong>Settings → Personal API Key</strong> and create a key. Garmin shows
          it only once.
        </li>
        <li>Paste it below. makerundev checks it with Garmin before saving it.</li>
      </ol>
      <p className="mt-3 text-sm text-muted-foreground">
        A key lasts 30 to 365 days, as chosen when it is created. When it runs out, create a new one and paste it here.
      </p>
    </section>
  );
}
