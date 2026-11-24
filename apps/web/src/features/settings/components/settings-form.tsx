import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, type SubmitEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  type FieldErrors,
  fieldKey,
  formValues,
  parseForm,
  refusedFields,
  type SettingsFormValues,
} from "@/features/settings/utils/settings-form";
import { getGetSettingsQueryKey, useSaveSettings } from "@/lib/api/endpoints/settings/settings.gen";
import type { SettingsSaved } from "@/lib/api/model/settings-saved.gen";
import type { SettingsView } from "@/lib/api/model/settings-view.gen";
import { TrimpCoefficients } from "@/lib/api/model/trimp-coefficients.gen";
import { ZoneModel } from "@/lib/api/model/zone-model.gen";
import { ApiError } from "@/lib/api-client";
import { activityCount, wholeNumber } from "@/lib/format";

const ZONE_MODELS: Record<ZoneModel, string> = {
  [ZoneModel.max_hr_percent]: "max heart rate",
  [ZoneModel.hr_reserve_percent]: "heart-rate reserve",
};
const COEFFICIENTS: Record<TrimpCoefficients, string> = {
  [TrimpCoefficients.male]: "Male",
  [TrimpCoefficients.female]: "Female",
};
const SELECT = "h-8 justify-self-start border border-rule bg-background px-2 text-[15px]";

function savedNotice({ trimp_recomputed, trimp_unreadable }: SettingsSaved): string {
  let notice = "Settings saved.";
  if (trimp_recomputed) notice += ` TRIMP recomputed for ${activityCount(trimp_recomputed)}.`;
  if (trimp_unreadable) notice += ` ${activityCount(trimp_unreadable)} could not be read; see the server log.`;
  return notice;
}

export function SettingsForm({ view }: { view: SettingsView }) {
  const queryClient = useQueryClient();
  const [values, setValues] = useState(() => formValues(view));
  const [errors, setErrors] = useState<FieldErrors>({});
  const [failed, setFailed] = useState(false);
  const save = useSaveSettings<unknown>({
    mutation: {
      onSuccess: (saved) => {
        const settingsKey = getGetSettingsQueryKey();
        const next = { ...view, settings: saved.settings, zone_starts_bpm: saved.zone_starts_bpm };
        queryClient.setQueryData(settingsKey, next);
        void queryClient.invalidateQueries({ predicate: (query) => query.queryKey[0] !== settingsKey[0] });
        setValues(formValues(next));
        setErrors({});
      },
      onError: (error) => {
        const refused = error instanceof ApiError && error.status === 422 ? refusedFields(error.body) : null;
        setErrors(refused ?? {});
        setFailed(refused === null);
      },
    },
  });

  function change<K extends keyof SettingsFormValues>(field: K, value: SettingsFormValues[K]) {
    setValues((current) => ({ ...current, [field]: value }));
  }

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    save.reset();
    setFailed(false);
    const parsed = parseForm(values);
    if ("errors" in parsed) {
      setErrors(parsed.errors);
      return;
    }
    setErrors({});
    save.mutate({ data: parsed.settings });
  }

  const invalid = Object.keys(errors).length > 0;
  const zoneStarts = invalid ? null : view.zone_starts_bpm;
  const highest = view.highest_heart_rate_bpm;

  return (
    <form noValidate onSubmit={submit} className="grid max-w-2xl gap-8">
      {save.isSuccess && (
        <p role="status" className="border-y border-border py-4">
          {savedNotice(save.data)}
        </p>
      )}
      {invalid && (
        <p role="alert" className="border-y border-border py-4 font-semibold">
          Some values need fixing. Nothing was saved.
        </p>
      )}
      {failed && (
        <p role="alert" className="border-y border-border py-4">
          Your settings could not be saved. Try again.
        </p>
      )}

      <Section legend="Heart rate">
        <div className="grid gap-x-6 gap-y-5 sm:grid-cols-3">
          <NumberField
            id="max_heart_rate_bpm"
            label="Max heart rate"
            suffix="bpm"
            whole
            errors={errors}
            hint={highest === null ? undefined : `Highest recorded in your activities: ${wholeNumber(highest, "bpm")}`}
            value={values.max_heart_rate_bpm}
            onChange={(value) => {
              change("max_heart_rate_bpm", value);
            }}
          />
          <NumberField
            id="resting_heart_rate_bpm"
            label="Resting heart rate"
            suffix="bpm"
            whole
            errors={errors}
            value={values.resting_heart_rate_bpm}
            onChange={(value) => {
              change("resting_heart_rate_bpm", value);
            }}
          />
          <Field
            id="trimp_coefficients"
            label="TRIMP coefficients"
            errors={errors}
            hint="Banister's weighting of heart-rate reserve."
          >
            {(props) => (
              <select
                {...props}
                className={SELECT}
                value={values.trimp_coefficients}
                onChange={(event) => {
                  change("trimp_coefficients", event.target.value as TrimpCoefficients);
                }}
              >
                {Object.entries(COEFFICIENTS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            )}
          </Field>
        </div>
      </Section>

      <Section legend="Body">
        <NumberField
          id="body_mass_kg"
          label="Body mass"
          suffix="kg"
          errors={errors}
          hint="Used for estimated power. Leave it blank if you don't want it."
          value={values.body_mass_kg}
          onChange={(value) => {
            change("body_mass_kg", value);
          }}
        />
      </Section>

      <Section legend="Zones">
        <p className="-mt-1 max-w-[65ch] text-sm text-muted-foreground">
          Where each zone starts, as a percentage of {ZONE_MODELS[values.zone_model]}. Zone 1 is everything below zone
          2.
        </p>
        <Field
          id="zone_model"
          label="Zone model"
          errors={errors}
          hint="A zone starts at max × % or, for reserve, at resting + (max − resting) × %."
        >
          {(props) => (
            <select
              {...props}
              className={SELECT}
              value={values.zone_model}
              onChange={(event) => {
                change("zone_model", event.target.value as ZoneModel);
              }}
            >
              {Object.entries(ZONE_MODELS).map(([value, label]) => (
                <option key={value} value={value}>
                  % of {label}
                </option>
              ))}
            </select>
          )}
        </Field>
        <div className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
          {values.zone_thresholds_percent.map((threshold, index) => {
            const start = zoneStarts?.[index];
            return (
              <NumberField
                key={index}
                id={fieldKey(["zone_thresholds_percent", index])}
                label={`Zone ${index + 2} starts at`}
                suffix="%"
                errors={errors}
                hint={start === undefined ? undefined : `${start} bpm`}
                value={threshold}
                onChange={(value) => {
                  change(
                    "zone_thresholds_percent",
                    values.zone_thresholds_percent.map((old, i) => (i === index ? value : old)),
                  );
                }}
              />
            );
          })}
        </div>
      </Section>

      <Section legend="Days">
        <Field
          id="timezone"
          label="Timezone"
          errors={errors}
          hint="Decides which day an activity counts toward in daily training load."
        >
          {(props) => (
            <>
              <Input
                {...props}
                list="timezones"
                autoComplete="off"
                className="max-w-72"
                value={values.timezone}
                onChange={(event) => {
                  change("timezone", event.target.value);
                }}
              />
              <datalist id="timezones">
                {view.timezones.map((name) => (
                  <option key={name} value={name} />
                ))}
              </datalist>
            </>
          )}
        </Field>
      </Section>

      <div>
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? "Saving" : "Save"}
        </Button>
      </div>
    </form>
  );
}

function Section({ legend, children }: { legend: string; children: ReactNode }) {
  return (
    <fieldset className="m-0 grid gap-5 border-0 p-0">
      <legend className="mb-4 w-full border-b border-rule pb-2 font-semibold">{legend}</legend>
      {children}
    </fieldset>
  );
}

type ControlProps = { id: string; name: string; "aria-invalid": boolean; "aria-describedby"?: string };

type FieldProps = {
  id: string;
  label: string;
  suffix?: string;
  hint?: string | undefined;
  errors: FieldErrors;
};

function NumberField({
  whole = false,
  value,
  onChange,
  ...field
}: FieldProps & { whole?: boolean; value: string; onChange: (value: string) => void }) {
  return (
    <Field {...field}>
      {(props) => (
        <Input
          {...props}
          inputMode={whole ? "numeric" : "decimal"}
          className="w-24 text-right font-semi-condensed font-medium"
          value={value}
          onChange={(event) => {
            onChange(event.target.value);
          }}
        />
      )}
    </Field>
  );
}

function Field({
  id,
  label,
  suffix,
  hint,
  errors,
  children,
}: FieldProps & { children: (props: ControlProps) => ReactNode }) {
  const error = errors[id];
  const note = error ?? hint;
  const control = children({
    id,
    name: id,
    "aria-invalid": error !== undefined,
    ...(note === undefined ? {} : { "aria-describedby": `${id}-note` }),
  });
  return (
    <div className="grid content-start gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {suffix ? (
        <span className="flex items-center gap-2">
          {control}
          <span className="text-sm text-muted-foreground">{suffix}</span>
        </span>
      ) : (
        control
      )}
      {note !== undefined && (
        <span id={`${id}-note`} className={error ? "text-sm font-semibold" : "text-sm text-muted-foreground"}>
          {note}
        </span>
      )}
    </div>
  );
}
