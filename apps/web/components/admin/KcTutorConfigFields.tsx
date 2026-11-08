"use client";

import { BLOCK_TYPES, type KcBlockType } from "@/lib/kc";
import {
  BLOCK_CONFIG_FIELDS,
  BLOCK_CONFIG_TITLES,
  OVERARCHING_FIELDS,
  type ConfigField,
  type KcTutorConfig,
} from "@/lib/kc-tutor-config";

export function KcTutorConfigFields({
  config,
  onChange,
}: {
  config: KcTutorConfig;
  onChange: (next: KcTutorConfig) => void;
}) {
  function setOver(key: string, value: string) {
    onChange({ ...config, overarching: { ...config.overarching, [key]: value } });
  }

  function setBlock(type: KcBlockType, key: string, value: string | number | boolean) {
    onChange({
      ...config,
      blocks: { ...config.blocks, [type]: { ...config.blocks[type], [key]: value } },
    });
  }

  return (
    <>
      <h3 className="agent-layer">Overarching, component framing</h3>
      <p className="help">These settings apply on every block while the tutor walks a knowledge component.</p>
      {OVERARCHING_FIELDS.map((field) => (
        <ConfigControl
          key={field.key}
          field={field}
          value={config.overarching[field.key]}
          onChange={(value) => setOver(field.key, String(value))}
        />
      ))}
      <h3 className="agent-layer">Block types</h3>
      {BLOCK_TYPES.map((type) => (
        <section key={type} aria-label={BLOCK_CONFIG_TITLES[type]}>
          <h3 className="agent-layer">{BLOCK_CONFIG_TITLES[type]}</h3>
          {BLOCK_CONFIG_FIELDS[type].map((field) => (
            <ConfigControl
              key={`${type}-${field.key}`}
              field={field}
              value={config.blocks[type]?.[field.key]}
              onChange={(value) => setBlock(type, field.key, value)}
            />
          ))}
        </section>
      ))}
    </>
  );
}

function ConfigControl({
  field,
  value,
  onChange,
}: {
  field: ConfigField;
  value: string | number | boolean | undefined;
  onChange: (value: string | number | boolean) => void;
}) {
  if (field.kind === "bool") {
    const checked = value !== false;
    return (
      <label className="check" title={field.help}>
        <input type="checkbox" checked={checked} title={field.help} onChange={(event) => onChange(event.target.checked)} />
        <span>
          {field.label}
          <span className="help">{field.help}</span>
        </span>
      </label>
    );
  }
  if (field.kind === "int") {
    const current = typeof value === "number" ? value : field.min;
    return (
      <label title={field.help}>
        {field.label}
        <span className="agent-level">{current}</span>
        <input
          type="range"
          min={field.min}
          max={field.max}
          step={1}
          value={current}
          title={field.help}
          aria-valuemin={field.min}
          aria-valuemax={field.max}
          aria-valuenow={current}
          aria-valuetext={`${current}. ${field.help}`}
          onChange={(event) => onChange(Number(event.target.value))}
        />
        <span className="agent-scale">
          <span>{field.min}</span>
          <span>{field.max}</span>
        </span>
        <span className="help">{field.help}</span>
      </label>
    );
  }
  const selected = typeof value === "string" ? value : field.options[0][0];
  return (
    <label title={field.help}>
      {field.label}
      <select title={field.help} value={selected} onChange={(event) => onChange(event.target.value)}>
        {field.options.map(([id, text]) => (
          <option key={id} value={id}>
            {text}
          </option>
        ))}
      </select>
      <span className="help">{field.help}</span>
    </label>
  );
}
