import { InlineCode, SectionHeading } from "@/features/strava/components/prose";

export function ConnectSteps({ callbackDomain }: { callbackDomain: string }) {
  return (
    <section className="mt-8 max-w-[65ch]">
      <SectionHeading>Set up your own Strava API application</SectionHeading>
      <ol className="mt-4 grid list-decimal gap-1.5 pl-5">
        <li>
          On Strava, open{" "}
          <a href="https://www.strava.com/settings/api" rel="noopener noreferrer" className="underline">
            Settings → My API Application
          </a>{" "}
          and create an application.
        </li>
        <li>
          Set its <strong>Authorization Callback Domain</strong> to <InlineCode>{callbackDomain}</InlineCode>.
        </li>
        <li>
          Start makerundev with the application&apos;s values in <InlineCode>MAKERUNDEV_STRAVA_CLIENT_ID</InlineCode>{" "}
          and <InlineCode>MAKERUNDEV_STRAVA_CLIENT_SECRET</InlineCode>.
        </li>
      </ol>
      <p className="mt-3 text-sm text-muted-foreground">
        The application is yours alone, so your data moves only between Strava and this machine.
      </p>
    </section>
  );
}
