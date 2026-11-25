const TIMEOUT_MS = 10_000;

export type SourceCheck = { kind: "custom_raster" | "custom_style"; url: string };

export function firstTileUrl(template: string): string {
  return template.replaceAll("{z}", "0").replaceAll("{x}", "0").replaceAll("{y}", "0");
}

function mixedContent(url: string): boolean {
  return window.location.protocol === "https:" && url.toLowerCase().startsWith("http:");
}

function loadImage(url: string): Promise<string | null> {
  return new Promise((resolve) => {
    const image = new Image();
    const timer = window.setTimeout(() => {
      image.src = "";
      resolve("The test tile did not arrive within 10 seconds.");
    }, TIMEOUT_MS);
    image.crossOrigin = "anonymous";
    image.onload = () => {
      window.clearTimeout(timer);
      resolve(null);
    };
    image.onerror = () => {
      window.clearTimeout(timer);
      resolve(
        "The test tile (zoom 0) could not be loaded as an image. The address may be wrong, the server down, or it does not allow this page to use its tiles (CORS).",
      );
    };
    image.src = url;
  });
}

async function loadStyle(url: string): Promise<string | null> {
  let response: Response;
  try {
    response = await fetch(url, { signal: AbortSignal.timeout(TIMEOUT_MS), credentials: "omit" });
  } catch {
    return "The style could not be fetched. The address may be wrong, the server down, or it does not allow this page to read it (CORS).";
  }
  if (!response.ok) return `The style address answered with HTTP ${response.status}.`;
  let style: unknown;
  try {
    style = await response.json();
  } catch {
    return "The style address did not return JSON.";
  }
  if (typeof style !== "object" || style === null || !("version" in style) || !("sources" in style)) {
    return "The address returned JSON that is not a MapLibre style: it has no version or sources.";
  }
  return null;
}

export async function checkSource({ kind, url }: SourceCheck): Promise<string | null> {
  if (!/^https?:\/\//i.test(url)) return null;
  if (mixedContent(url)) {
    return "This page is served over https://, so the browser blocks an http:// address as mixed content.";
  }
  return kind === "custom_raster" ? loadImage(firstTileUrl(url)) : loadStyle(url);
}
