import type { MapSource } from "@/lib/api/model/map-source.gen";

const LINK = "text-foreground underline";

function hostOf(url: string): string | null {
  try {
    return new URL(url).hostname || null;
  } catch {
    return null;
  }
}

export function MapNotice({
  id,
  preset,
  custom,
}: {
  id: string;
  preset: MapSource | null;
  custom: { kind: "custom_raster" | "custom_style"; url: string } | null;
}) {
  const provider = preset?.provider ?? (custom ? hostOf(custom.url.trim()) : null) ?? "the tile server";
  if (preset === null && custom === null) {
    return (
      <p id={id} className="max-w-[65ch] text-sm text-muted-foreground">
        The activity page draws the route shape, and nothing is requested from another host.
      </p>
    );
  }
  return (
    <p id={id} className="max-w-[65ch] text-sm text-muted-foreground">
      Map tiles are loaded by your browser straight from {provider}. Each time you open an activity, {provider} receives
      your IP address, your browser&apos;s details, this instance&apos;s address, and which tiles you view, which shows
      where the route is to within a few hundred metres.
      {preset?.terms_url && preset.privacy_url && (
        <>
          {" "}
          Their{" "}
          <a href={preset.terms_url} rel="noopener noreferrer" target="_blank" className={LINK}>
            terms
          </a>{" "}
          and{" "}
          <a href={preset.privacy_url} rel="noopener noreferrer" target="_blank" className={LINK}>
            privacy policy
          </a>{" "}
          apply.
        </>
      )}
      {custom?.kind === "custom_style" && " A style can load tiles, fonts and icons from other hosts."} To keep
      everything on your server, use a local tile file instead.
    </p>
  );
}
