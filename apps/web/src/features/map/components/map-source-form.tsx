import { useQueryClient } from "@tanstack/react-query";
import { type SubmitEvent, useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MapNotice } from "@/features/map/components/map-notice";
import { checkLocalFile } from "@/features/map/utils/check-local-file";
import { checkSource } from "@/features/map/utils/check-source";
import { getGetMapSourceQueryKey, useRemoveMapSource, useSaveMapSource } from "@/lib/api/endpoints/map/map.gen";
import type { HTTPValidationError } from "@/lib/api/model/httpvalidation-error.gen";
import type { MapSourceView } from "@/lib/api/model/map-source-view.gen";
import type { MapTileFile } from "@/lib/api/model/map-tile-file.gen";
import { MapSourceKind } from "@/lib/api/model/map-source-kind.gen";
import { ApiError } from "@/lib/api-client";

type Choice = MapSourceKind | "none";
type CustomKind = typeof MapSourceKind.custom_raster | typeof MapSourceKind.custom_style;
type Errors = { url?: string; attribution?: string; file?: string };

const SELECT = "h-8 justify-self-start border border-rule bg-background px-2 text-[15px]";
const MAP_DOCS = "https://github.com/tanhtruong/makerundev/blob/main/docs/map.md";

const OPTIONS: { value: Choice; label: string }[] = [
  { value: "none", label: "No map" },
  { value: MapSourceKind.openstreetmap, label: "OpenStreetMap" },
  { value: MapSourceKind.openfreemap, label: "OpenFreeMap" },
  { value: MapSourceKind.custom_raster, label: "Custom raster tiles" },
  { value: MapSourceKind.custom_style, label: "Custom map style" },
  { value: MapSourceKind.pmtiles, label: "Local tile file" },
];

function isCustom(choice: Choice): choice is CustomKind {
  return choice === MapSourceKind.custom_raster || choice === MapSourceKind.custom_style;
}

function refused(error: unknown): Errors | null {
  if (!(error instanceof ApiError) || error.status !== 422) return null;
  const errors: Errors = {};
  for (const { loc, msg } of (error.body as HTTPValidationError | null)?.detail ?? []) {
    const field = loc[1];
    if (field === "url" || field === "attribution" || field === "file") errors[field] = msg;
  }
  return Object.keys(errors).length > 0 ? errors : null;
}

function fileSize(bytes: number): string {
  if (bytes < 1_000_000) return `${String(Math.max(1, Math.round(bytes / 1000)))} KB`;
  return `${(bytes / 1_000_000).toLocaleString("en", { maximumFractionDigits: 1 })} MB`;
}

function tilesUrl(file: string): string {
  return `/tiles/${encodeURIComponent(file)}`;
}

export function MapSourceForm({ view }: { view: MapSourceView }) {
  const id = useId();
  const queryClient = useQueryClient();
  const saved = view.source;
  const [choice, setChoice] = useState<Choice>(saved?.kind ?? "none");
  const [url, setUrl] = useState(saved && isCustom(saved.kind) ? saved.url : "");
  const [attribution, setAttribution] = useState(saved && isCustom(saved.kind) ? saved.attribution : "");
  const [file, setFile] = useState(
    view.files.find((listed) => listed.name === saved?.file)?.name ?? view.files[0]?.name ?? "",
  );
  const [errors, setErrors] = useState<Errors>({});
  const [warning, setWarning] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [notice, setNotice] = useState<"saved" | "failed" | null>(null);

  const mutation = {
    onSuccess: (next: MapSourceView) => {
      queryClient.setQueryData(getGetMapSourceQueryKey(), next);
      setErrors({});
      setNotice("saved");
    },
    onError: (error: unknown) => {
      const fields = refused(error);
      setErrors(fields ?? {});
      setNotice(fields ? null : "failed");
    },
  };
  const save = useSaveMapSource<unknown>({ mutation });
  const remove = useRemoveMapSource({ mutation });
  const busy = checking || save.isPending || remove.isPending;

  function choose(next: Choice) {
    setChoice(next);
    setErrors({});
    setWarning(null);
    setNotice(null);
  }

  function send() {
    setWarning(null);
    if (choice === "none") {
      remove.mutate();
      return;
    }
    if (choice === MapSourceKind.pmtiles) {
      save.mutate({ data: { kind: choice, url: null, attribution: null, file } });
      return;
    }
    const custom = isCustom(choice);
    save.mutate({
      data: { kind: choice, url: custom ? url.trim() : null, attribution: custom ? attribution : null },
    });
  }

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice(null);
    setWarning(null);
    const local = choice === MapSourceKind.pmtiles && file !== "";
    if (isCustom(choice) || local) {
      setChecking(true);
      const problem = isCustom(choice)
        ? await checkSource({ kind: choice, url: url.trim() })
        : await checkLocalFile(tilesUrl(file));
      setChecking(false);
      if (problem !== null) {
        setWarning(problem);
        return;
      }
    }
    send();
  }

  const preset = view.presets.find((candidate) => candidate.kind === choice) ?? null;
  const custom = isCustom(choice) ? { kind: choice, url } : null;
  const urlLabel = choice === MapSourceKind.custom_style ? "Style URL" : "Tile URL";
  const urlHint =
    choice === MapSourceKind.custom_style
      ? "The address of a MapLibre style.json. An API key in it is visible to anyone who can open this app."
      : "An https:// template with {z}, {x} and {y}, such as https://tiles.example.com/{z}/{x}/{y}.png. An API key in it is visible to anyone who can open this app.";

  return (
    <form noValidate onSubmit={(event) => void submit(event)} className="max-w-2xl">
      <fieldset className="m-0 grid gap-5 border-0 p-0">
        <legend className="mb-4 w-full border-b border-rule pb-2 font-semibold">Map</legend>
        {notice === "saved" && (
          <p role="status" className="border-y border-border py-4">
            {choice === "none" ? "Map turned off." : "Map source saved."}
          </p>
        )}
        {notice === "failed" && (
          <p role="alert" className="border-y border-border py-4">
            The map source could not be saved. Try again.
          </p>
        )}
        <div role="radiogroup" aria-label="Map source" className="grid gap-2">
          {OPTIONS.map((option) => (
            <label key={option.value} className="flex items-center gap-2">
              <input
                type="radio"
                name="map-source"
                value={option.value}
                checked={choice === option.value}
                onChange={() => {
                  choose(option.value);
                }}
                className="size-4 accent-foreground"
              />
              {option.label}
            </label>
          ))}
        </div>
        <MapNotice id={`${id}-notice`} local={choice === MapSourceKind.pmtiles} preset={preset} custom={custom} />
        {choice === MapSourceKind.pmtiles && (
          <LocalFileField
            id={`${id}-file`}
            files={view.files}
            missing={saved?.kind === MapSourceKind.pmtiles && saved.file_missing ? saved.file : null}
            error={errors.file}
            value={file}
            onChange={setFile}
          />
        )}
        {custom && (
          <div className="grid gap-5">
            <TextField
              id={`${id}-url`}
              label={urlLabel}
              hint={urlHint}
              error={errors.url}
              value={url}
              onChange={setUrl}
            />
            <TextField
              id={`${id}-attribution`}
              label="Attribution"
              hint="Shown on the map, as plain text. Use the credit your provider asks for."
              error={errors.attribution}
              value={attribution}
              onChange={setAttribution}
            />
          </div>
        )}
        {warning !== null && (
          <div role="alert" className="grid gap-3 border-y border-border py-4">
            <p>{warning}</p>
            <div>
              <Button type="button" onClick={send} disabled={busy}>
                Save anyway
              </Button>
            </div>
          </div>
        )}
        <div>
          <Button type="submit" disabled={busy}>
            {checking ? "Checking" : save.isPending || remove.isPending ? "Saving" : "Save map"}
          </Button>
        </div>
      </fieldset>
    </form>
  );
}

function LocalFileField({
  id,
  files,
  missing,
  error,
  value,
  onChange,
}: {
  id: string;
  files: MapTileFile[];
  missing: string | null;
  error: string | undefined;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="grid content-start gap-1.5">
      {missing !== null && <p className="font-semibold">The tile file {missing} is not in the data directory.</p>}
      {files.length === 0 ? (
        <p className="max-w-[65ch] text-sm">
          No .pmtiles file found in the data directory. See the{" "}
          <a href={MAP_DOCS} rel="noopener noreferrer" target="_blank" className="underline">
            map docs
          </a>{" "}
          for how to make one.
        </p>
      ) : (
        <>
          <Label htmlFor={id}>Tile file</Label>
          <select
            id={id}
            className={SELECT}
            value={value}
            aria-invalid={error !== undefined}
            aria-describedby={`${id}-note`}
            onChange={(event) => {
              onChange(event.target.value);
            }}
          >
            {files.map((listed) => (
              <option key={listed.name} value={listed.name}>
                {listed.name} ({fileSize(listed.size_bytes)})
              </option>
            ))}
          </select>
          <span id={`${id}-note`} className={error ? "text-sm font-semibold" : "text-sm text-muted-foreground"}>
            {error ?? "A .pmtiles file in the top level of the data directory."}
          </span>
        </>
      )}
      {files.length === 0 && error !== undefined && <span className="text-sm font-semibold">{error}</span>}
    </div>
  );
}

function TextField({
  id,
  label,
  hint,
  error,
  value,
  onChange,
}: {
  id: string;
  label: string;
  hint: string;
  error: string | undefined;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="grid content-start gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        autoComplete="off"
        spellCheck={false}
        value={value}
        aria-invalid={error !== undefined}
        aria-describedby={`${id}-note`}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      />
      <span id={`${id}-note`} className={error ? "text-sm font-semibold" : "text-sm text-muted-foreground"}>
        {error ?? hint}
      </span>
    </div>
  );
}
