import { useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { getListActivitiesQueryKey, useImportActivities } from "@/lib/api/endpoints/activities/activities.gen";
import type { FileImport } from "@/lib/api/model/file-import.gen";
import { ApiError } from "@/lib/api-client";

const ACCEPT = ".fit,.gpx,.tcx,.gz,.zip";
const OUTCOME = { imported: "Imported", already_imported: "Already imported" };

export function ImportForm() {
  const queryClient = useQueryClient();
  const form = useRef<HTMLFormElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const upload = useImportActivities({
    mutation: {
      onSuccess: () => queryClient.invalidateQueries({ queryKey: getListActivitiesQueryKey() }),
    },
  });

  function send() {
    upload.mutate(
      { data: { files } },
      {
        onSuccess: () => {
          form.current?.reset();
          setFiles([]);
        },
      },
    );
  }

  return (
    <section className={`mb-6 border-t border-border pt-5 ${upload.isSuccess ? "" : "border-b pb-5"}`}>
      <form
        ref={form}
        onSubmit={(event) => {
          event.preventDefault();
          send();
        }}
        className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3"
      >
        <div className="grid min-w-0 gap-1">
          <label htmlFor="import-files" className="font-semibold">
            Import activities
          </label>
          <span id="import-hint" className="text-sm text-muted-foreground">
            FIT, GPX or TCX, optionally gzipped or zipped. Choose several at once.
          </span>
          <div className="mt-2 flex min-w-0 items-center gap-3">
            <input
              id="import-files"
              type="file"
              name="files"
              multiple
              accept={ACCEPT}
              aria-describedby="import-hint"
              onChange={(event) => {
                setFiles(Array.from(event.currentTarget.files ?? []));
              }}
              className="peer sr-only"
            />
            <Button
              asChild
              className="cursor-pointer peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-ring"
            >
              <label htmlFor="import-files">Choose files</label>
            </Button>
            <span className="min-w-0 truncate text-sm text-muted-foreground">{chosen(files)}</span>
          </div>
        </div>
        <Button type="submit" disabled={files.length === 0 || upload.isPending}>
          {upload.isPending ? "Importing" : "Import"}
        </Button>
      </form>
      {upload.isError && (
        <div role="alert" className="mt-5 flex flex-wrap items-center gap-4 border-t border-border pt-5">
          <span>The files could not be imported: {failure(upload.error)}</span>
          <Button onClick={send}>Try again</Button>
        </div>
      )}
      {upload.data && <ImportResults results={upload.data.results} />}
    </section>
  );
}

function ImportResults({ results }: { results: FileImport[] }) {
  return (
    <ul aria-label="Import results" className="mt-4 border-t border-rule">
      {results.map((result, index) => (
        <li
          key={index}
          className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-0.5 border-b border-border py-2.5"
        >
          {result.activity_id === null ? (
            <span className="min-w-0 truncate font-medium">{result.filename}</span>
          ) : (
            <Link
              to="/activities/$activityId"
              params={{ activityId: result.activity_id }}
              className="min-w-0 truncate font-medium hover:underline"
            >
              {result.filename}
            </Link>
          )}
          {result.status === "failed" ? (
            <span>{result.error}</span>
          ) : (
            <span className="text-muted-foreground">{OUTCOME[result.status]}</span>
          )}
        </li>
      ))}
    </ul>
  );
}

function chosen(files: File[]): string {
  if (files.length === 0) return "No files chosen";
  if (files.length === 1) return files[0]?.name ?? "";
  return `${files.length} files chosen`;
}

function failure(error: unknown): string {
  if (!(error instanceof ApiError)) return "the server could not be reached.";
  const detail = (error.body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item: { msg?: string }) => item.msg ?? "").join("; ");
  return `the server answered ${error.status}.`;
}
