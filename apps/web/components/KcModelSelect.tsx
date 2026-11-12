import { DEFAULT_KC_MODEL, KC_MODEL_OPTIONS, kcModel } from "@/lib/kc-models";

export function KcModelSelect({ value }: { value?: string }) {
  const selected = value ? kcModel(value) : DEFAULT_KC_MODEL;
  return (
    <label className="kc-model">
      Model
      <select name="model" aria-label="Model" defaultValue={selected}>
        {KC_MODEL_OPTIONS.map(([id, label]) => (
          <option key={id} value={id}>
            {label}
          </option>
        ))}
      </select>
    </label>
  );
}
