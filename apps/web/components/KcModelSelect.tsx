import { DEFAULT_KC_MODEL, KC_MODELS, kcModel } from "@/lib/kc-models";

export function KcModelSelect({ value }: { value?: string }) {
  const selected = value ? kcModel(value) : DEFAULT_KC_MODEL;
  return (
    <label className="kc-model">
      Model
      <select name="model" aria-label="Model" defaultValue={selected}>
        {KC_MODELS.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}
