"use client";

import { useMemo, useState, type ChangeEvent } from "react";

import {
  DEFAULT_AVATAR_PRESET,
  TUTOR_AVATAR_CATEGORIES,
  TUTOR_AVATAR_PRESETS,
  getTutorAvatarPreset,
  type TutorAvatarCategoryId,
} from "@/lib/tutor-avatars";

const SIZE_PX = {
  sm: 24,
  md: 36,
  lg: 52,
  xl: 88,
} as const;

export function TutorAvatar({
  preset,
  avatarUrl,
  name,
  size = "md",
  className = "",
}: {
  preset?: string | null;
  avatarUrl?: string | null;
  name?: string;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}) {
  const px = SIZE_PX[size];
  const resolved = getTutorAvatarPreset(preset);
  const cleanedUrl = (avatarUrl ?? "").trim();
  const label = name ? `${name} avatar` : resolved.label;

  if (cleanedUrl) {
    return (
      <span
        className={`tutor-avatar tutor-avatar-${size} ${className}`.trim()}
        style={{
          width: px,
          height: px,
          minWidth: px,
          minHeight: px,
          borderRadius: "9999px",
          overflow: "hidden",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#e2e8f0",
          border: "1px solid rgba(15, 23, 42, 0.12)",
        }}
        title={label}
      >
        <img
          src={cleanedUrl}
          alt={label}
          width={px}
          height={px}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </span>
    );
  }

  return (
    <span
      className={`tutor-avatar tutor-avatar-${size} ${className}`.trim()}
      data-avatar-preset={resolved.id}
      style={{
        width: px,
        height: px,
        minWidth: px,
        minHeight: px,
        borderRadius: "9999px",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: resolved.bg,
        color: resolved.fg,
        border: "1px solid rgba(15, 23, 42, 0.12)",
      }}
      title={label}
    >
      {resolved.id === DEFAULT_AVATAR_PRESET ? (
        <svg
          width={Math.round(px * 0.55)}
          height={Math.round(px * 0.55)}
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="6" fill={resolved.fg} opacity="0.35" />
        </svg>
      ) : (
        <svg
          width={Math.round(px * 0.62)}
          height={Math.round(px * 0.62)}
          viewBox="0 0 24 24"
          fill="none"
          stroke={resolved.fg}
          strokeWidth="1.9"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          {resolved.paths.map((d, idx) => (
            <path key={idx} d={d} />
          ))}
        </svg>
      )}
    </span>
  );
}

export function TutorAvatarPicker({
  preset,
  avatarUrl,
  onChangePreset,
  onChangeUrl,
}: {
  preset: string;
  avatarUrl?: string | null;
  onChangePreset: (nextPreset: string) => void;
  onChangeUrl: (nextUrl: string | null) => void;
}) {
  const [category, setCategory] = useState<"all" | TutorAvatarCategoryId>("all");
  const [query, setQuery] = useState("");
  const currentPreset = getTutorAvatarPreset(preset);

  const filteredPresets = useMemo(() => {
    const q = query.trim().toLowerCase();
    return TUTOR_AVATAR_PRESETS.filter((item) => {
      if (category !== "all" && item.category !== category) return false;
      if (!q) return true;
      const hay = `${item.id} ${item.label} ${item.keywords}`.toLowerCase();
      return q.split(/\s+/).every((tok) => hay.includes(tok));
    });
  }, [category, query]);

  function handleFileUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = typeof reader.result === "string" ? reader.result : null;
      if (!dataUrl) return;
      const img = new Image();
      img.onload = () => {
        try {
          const canvas = document.createElement("canvas");
          canvas.width = 128;
          canvas.height = 128;
          const ctx = canvas.getContext("2d");
          if (ctx) {
            ctx.drawImage(img, 0, 0, 128, 128);
            onChangeUrl(canvas.toDataURL("image/png"));
            return;
          }
        } catch {
          // Fall back to raw dataUrl below
        }
        onChangeUrl(dataUrl);
      };
      img.onerror = () => {
        onChangeUrl(dataUrl);
      };
      img.src = dataUrl;
    };
    reader.readAsDataURL(file);
  }

  return (
    <div className="tutor-avatar-picker" aria-label="Tutor Avatar Picker">
      <div className="tutor-avatar-preview-row">
        <TutorAvatar preset={preset} avatarUrl={avatarUrl} size="lg" />
        <div className="tutor-avatar-preview-meta">
          <strong>
            {avatarUrl ? "Custom Image Avatar" : currentPreset.label}
          </strong>
          <span className="help">
            Choose from 64 built-in circular SVG icons across 8 categories, or upload a custom image.
          </span>
        </div>
        <button
          type="button"
          className="ghost"
          onClick={() => {
            onChangePreset(DEFAULT_AVATAR_PRESET);
            onChangeUrl(null);
          }}
        >
          Reset to Gray Circle
        </button>
      </div>

      <div className="tutor-avatar-filter-bar">
        <div className="kc-chip-group" role="group" aria-label="Avatar categories">
          <button
            type="button"
            className={`kc-chip${category === "all" ? " is-active" : ""}`}
            aria-pressed={category === "all"}
            onClick={() => setCategory("all")}
          >
            All 64
          </button>
          {TUTOR_AVATAR_CATEGORIES.map((cat) => (
            <button
              key={cat.id}
              type="button"
              className={`kc-chip${category === cat.id ? " is-active" : ""}`}
              aria-pressed={category === cat.id}
              onClick={() => setCategory(cat.id)}
            >
              {cat.shortLabel}
            </button>
          ))}
        </div>
        <input
          type="search"
          aria-label="Search avatar icons"
          placeholder="Search 64 icons (e.g. owl, dragon, robot, rocket, compass)..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      <div className="tutor-avatar-grid" role="listbox" aria-label="64 built-in tutor avatars">
        {filteredPresets.map((item) => {
          const isSelected = !avatarUrl && currentPreset.id === item.id;
          return (
            <button
              key={item.id}
              type="button"
              role="option"
              aria-selected={isSelected}
              aria-label={item.label}
              title={item.label}
              className={`tutor-avatar-option${isSelected ? " is-selected" : ""}`}
              onClick={() => {
                onChangePreset(item.id);
                onChangeUrl(null);
              }}
            >
              <TutorAvatar preset={item.id} size="md" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>

      <div className="tutor-avatar-custom-row">
        <label>
          Custom Image URL
          <input
            type="text"
            aria-label="Custom Image URL"
            placeholder="https://... or upload an image file"
            value={avatarUrl ?? ""}
            onChange={(event) => onChangeUrl(event.target.value.trim() || null)}
          />
        </label>
        <label className="tutor-avatar-upload-label">
          Upload Image File
          <input
            type="file"
            accept="image/png,image/jpeg,image/svg+xml,image/webp"
            onChange={handleFileUpload}
          />
        </label>
      </div>
    </div>
  );
}
