/**
 * LanguagePicker
 *
 * Compact dropdown for selecting the user's preferred response language.
 * - On mount: fetches GET /preferences to restore the stored value.
 * - On change: calls PUT /preferences and stores the value in localStorage.
 * - Exposes the selected language code via the `onChange` callback so the parent
 *   can pass it to API requests.
 */

import React, { useEffect, useRef, useState } from "react";
import { FiGlobe, FiCheck } from "react-icons/fi";
import { apiFetch } from "../services/api";

// Languages shown prominently in the picker (most likely for Indian students).
const PRIORITY_CODES = ["en", "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml"];

export default function LanguagePicker({ onChange, compact = false }) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState("en");
  const [languages, setLanguages] = useState([]);
  const [loading, setLoading] = useState(false);
  const dropRef = useRef(null);

  /* ── Load language list + stored preference ──────────────────────────── */
  useEffect(() => {
    let cancelled = false;

    async function init() {
      // Language catalogue — public endpoint, no auth required
      try {
        const res = await apiFetch("/languages");
        const data = await res.json();
        if (!cancelled && data.languages) {
          setLanguages(data.languages);
        }
      } catch {
        // silently ignore — UI still works with fallback list
      }

      // Stored preference
      try {
        const res = await apiFetch("/preferences");
        const pref = await res.json();
        if (!cancelled && pref.preferred_language) {
          setSelected(pref.preferred_language);
          onChange?.(pref.preferred_language);
        }
      } catch {
        const cached = localStorage.getItem("preferred_language");
        if (!cancelled && cached) {
          setSelected(cached);
          onChange?.(cached);
        }
      }
    }

    init();
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── Close on outside click ──────────────────────────────────────────── */
  useEffect(() => {
    function handleClick(e) {
      if (dropRef.current && !dropRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  /* ── Select a language ───────────────────────────────────────────────── */
  async function handleSelect(code) {
    setOpen(false);
    if (code === selected) return;
    setSelected(code);
    localStorage.setItem("preferred_language", code);
    onChange?.(code);
    setLoading(true);
    try {
      await apiFetch("/preferences", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preferred_language: code }),
      });
    } catch {
      // best-effort; localStorage already stores the choice
    } finally {
      setLoading(false);
    }
  }

  /* ── Render ───────────────────────────────────────────────────────────── */
  const selectedLabel =
    languages.find((l) => l.code === selected)?.name || selected.toUpperCase();

  // Sort languages: priority codes first, then rest alphabetically
  const sorted = [
    ...PRIORITY_CODES.map((c) => languages.find((l) => l.code === c)).filter(Boolean),
    ...languages.filter((l) => !PRIORITY_CODES.includes(l.code)).sort((a, b) =>
      a.name.localeCompare(b.name)
    ),
  ];

  return (
    <div className="lang-picker" ref={dropRef}>
      <button
        type="button"
        className={`lang-picker__trigger ${loading ? "lang-picker__trigger--loading" : ""}`}
        onClick={() => setOpen((o) => !o)}
        title="Response language"
        aria-label={`Response language: ${selectedLabel}`}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <FiGlobe aria-hidden="true" />
        {!compact && <span className="lang-picker__label">{selectedLabel}</span>}
      </button>

      {open && (
        <div className="lang-picker__dropdown" role="listbox" aria-label="Select language">
          {sorted.length === 0 ? (
            <div className="lang-picker__empty">Loading languages…</div>
          ) : (
            sorted.map((lang) => (
              <button
                key={lang.code}
                type="button"
                role="option"
                aria-selected={lang.code === selected}
                className={`lang-picker__option ${lang.code === selected ? "lang-picker__option--active" : ""}`}
                onClick={() => handleSelect(lang.code)}
              >
                <span className="lang-picker__option-name">{lang.name}</span>
                <span className="lang-picker__option-code">{lang.code}</span>
                {lang.code === selected && <FiCheck className="lang-picker__check" aria-hidden="true" />}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
