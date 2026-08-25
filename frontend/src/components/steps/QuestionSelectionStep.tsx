"use client";

import React, { useState } from "react";
import { SelectionMode } from "../../types";
import {
  SelectionIcon,
  CheckIcon,
  XIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
} from "../icons";

interface QuestionSelectionStepProps {
  rawQuestions: Record<string, any>[];
  selectedIndices: number[];
  onSelectionChange: (selectedIndices: number[]) => void;
  onBack: () => void;
  onNext: () => void;
}

export default function QuestionSelectionStep({
  rawQuestions,
  selectedIndices,
  onSelectionChange,
  onBack,
  onNext,
}: QuestionSelectionStepProps) {
  const totalDetected = rawQuestions.length;
  const [mode, setMode] = useState<SelectionMode>("all");
  const [targetCount, setTargetCount] = useState<number>(Math.min(10, totalDetected));
  const [rangeInput, setRangeInput] = useState<string>("1-10");

  const handleModeChange = (newMode: SelectionMode) => {
    setMode(newMode);
    if (newMode === "all") {
      onSelectionChange(rawQuestions.map((_, i) => i));
    } else if (newMode === "count") {
      const count = Math.min(targetCount, totalDetected);
      onSelectionChange(Array.from({ length: count }, (_, i) => i));
    }
  };

  const handleTargetCountChange = (count: number) => {
    const validCount = Math.max(1, Math.min(count, totalDetected));
    setTargetCount(validCount);
    if (mode === "count") {
      onSelectionChange(Array.from({ length: validCount }, (_, i) => i));
    }
  };

  const toggleQuestion = (index: number) => {
    if (selectedIndices.includes(index)) {
      onSelectionChange(selectedIndices.filter((i) => i !== index));
    } else {
      onSelectionChange([...selectedIndices, index].sort((a, b) => a - b));
    }
  };

  const handleSelectAll = () => {
    onSelectionChange(rawQuestions.map((_, i) => i));
  };

  const handleClearAll = () => {
    onSelectionChange([]);
  };

  const handleApplyRange = () => {
    try {
      const parts = rangeInput.split("-").map((s) => parseInt(s.trim(), 10));
      if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
        const start = Math.max(1, parts[0]) - 1;
        const end = Math.min(totalDetected, parts[1]) - 1;
        const indices: number[] = [];
        for (let i = start; i <= end; i++) {
          indices.push(i);
        }
        onSelectionChange(indices);
      }
    } catch (e) {
      console.error("Invalid range:", e);
    }
  };

  return (
    <section className="card">
      <div className="card-header-flex">
        <div>
          <div className="card-title">
            <SelectionIcon size={22} color="var(--primary-hover)" /> Step 3: Question Ingestion & Selection Control
          </div>
          <div className="card-subtitle">
            The parser extracted <strong>{totalDetected} questions</strong> from the source file. Select which questions will proceed through mapping, validation, review, and final export.
          </div>
        </div>
        <span className="badge info">Step 03 / 08</span>
      </div>

      {/* Control Bar */}
      <div
        style={{
          background: "var(--bg-surface)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "14px",
          padding: "20px",
          marginBottom: "24px",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "16px", marginBottom: "16px" }}>
          <div>
            <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)", textTransform: "uppercase", fontWeight: 700 }}>
              Selection Mode
            </span>
            <div style={{ display: "flex", gap: "16px", marginTop: "8px" }}>
              <label style={{ display: "inline-flex", alignItems: "center", gap: "6px", cursor: "pointer", fontSize: "0.9rem", color: "var(--text-primary)" }}>
                <input
                  type="radio"
                  name="selectionMode"
                  checked={mode === "all"}
                  onChange={() => handleModeChange("all")}
                />
                All Extracted Questions ({totalDetected})
              </label>

              <label style={{ display: "inline-flex", alignItems: "center", gap: "6px", cursor: "pointer", fontSize: "0.9rem", color: "var(--text-primary)" }}>
                <input
                  type="radio"
                  name="selectionMode"
                  checked={mode === "count"}
                  onChange={() => handleModeChange("count")}
                />
                Select Number
              </label>

              <label style={{ display: "inline-flex", alignItems: "center", gap: "6px", cursor: "pointer", fontSize: "0.9rem", color: "var(--text-primary)" }}>
                <input
                  type="radio"
                  name="selectionMode"
                  checked={mode === "custom"}
                  onChange={() => handleModeChange("custom")}
                />
                Custom Checkboxes
              </label>
            </div>
          </div>

          {/* Active Selection Badge */}
          <div style={{ textAlign: "right" }}>
            <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)", textTransform: "uppercase", fontWeight: 700 }}>
              Selection Status
            </span>
            <div style={{ fontSize: "1.2rem", fontWeight: 800, color: selectedIndices.length > 0 ? "var(--accent)" : "var(--danger)", marginTop: "4px" }}>
              {selectedIndices.length} / {totalDetected} Selected
            </div>
          </div>
        </div>

        {/* Dynamic Controls based on mode */}
        {mode === "count" && (
          <div style={{ display: "flex", alignItems: "center", gap: "14px", borderTop: "1px solid var(--border-subtle)", paddingTop: "14px" }}>
            <span style={{ fontSize: "0.86rem", color: "var(--text-secondary)" }}>
              Take first:
            </span>
            <input
              type="number"
              min={1}
              max={totalDetected}
              value={targetCount}
              onChange={(e) => handleTargetCountChange(parseInt(e.target.value, 10) || 1)}
              style={{ width: "100px", padding: "6px 12px" }}
            />
            <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
              questions out of {totalDetected} extracted items (subsets directly without generating questions).
            </span>
          </div>
        )}

        {mode === "custom" && (
          <div style={{ display: "flex", alignItems: "center", gap: "12px", borderTop: "1px solid var(--border-subtle)", paddingTop: "14px", flexWrap: "wrap" }}>
            <button className="secondary" onClick={handleSelectAll} style={{ padding: "6px 12px", fontSize: "0.8rem", gap: "4px" }}>
              <CheckIcon size={14} /> Select All
            </button>
            <button className="secondary" onClick={handleClearAll} style={{ padding: "6px 12px", fontSize: "0.8rem", gap: "4px" }}>
              <XIcon size={14} /> Clear All
            </button>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginLeft: "auto" }}>
              <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Range:</span>
              <input
                type="text"
                placeholder="e.g. 1-10"
                value={rangeInput}
                onChange={(e) => setRangeInput(e.target.value)}
                style={{ width: "90px", padding: "4px 8px", fontSize: "0.8rem" }}
              />
              <button className="secondary" onClick={handleApplyRange} style={{ padding: "4px 10px", fontSize: "0.8rem" }}>
                Apply
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Questions Preview List */}
      <div style={{ display: "flex", flexDirection: "column", gap: "10px", maxHeight: "480px", overflowY: "auto", paddingRight: "6px" }}>
        {rawQuestions.map((q, idx) => {
          const isSelected = selectedIndices.includes(idx);
          const questionText = q.question || q.question_text || q.prompt || Object.values(q)[0] || `Question #${idx + 1}`;
          const options = Array.isArray(q.options) ? q.options : [q.option_1, q.option_2, q.option_3, q.option_4].filter(Boolean);
          const answer = q.correct_answer || q.answer || "";

          return (
            <div
              key={idx}
              onClick={() => toggleQuestion(idx)}
              style={{
                background: isSelected ? "rgba(59, 130, 246, 0.08)" : "var(--bg-surface)",
                border: `1px solid ${isSelected ? "rgba(59, 130, 246, 0.4)" : "var(--border-subtle)"}`,
                borderRadius: "10px",
                padding: "14px 18px",
                display: "flex",
                alignItems: "flex-start",
                gap: "14px",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              <input
                type="checkbox"
                checked={isSelected}
                onChange={() => {}}
                style={{ marginTop: "4px", width: "16px", height: "16px", cursor: "pointer" }}
              />

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px", flexWrap: "wrap" }}>
                  <strong style={{ color: isSelected ? "var(--primary-hover)" : "var(--text-primary)", fontSize: "0.88rem" }}>
                    {q.sequence_id || `Q${idx + 1}`}
                  </strong>
                  {q.question_type && (
                    <span className="badge secondary" style={{ fontSize: "0.65rem", padding: "1px 6px" }}>
                      {q.question_type}
                    </span>
                  )}
                  {q.section && q.section !== "General" && (
                    <span className="badge warning" style={{ fontSize: "0.65rem", padding: "1px 6px" }}>
                      {q.section}
                    </span>
                  )}
                  {q.source_page && (
                    <span className="badge info" style={{ fontSize: "0.65rem", padding: "1px 6px" }}>
                      Page {q.source_page}
                    </span>
                  )}
                  {answer && (
                    <span className="badge success" style={{ fontSize: "0.65rem", padding: "1px 6px" }}>
                      Answer: {answer}
                    </span>
                  )}
                </div>

                <div style={{ fontSize: "0.84rem", color: "var(--text-primary)", lineHeight: "1.4", marginBottom: "6px" }}>
                  {questionText}
                </div>

                {options.length > 0 && (
                  <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    {options.map((opt: any, optIdx: number) => (
                      <span key={optIdx} style={{ background: "rgba(0,0,0,0.2)", padding: "2px 8px", borderRadius: "4px" }}>
                        ({String.fromCharCode(65 + optIdx)}) {String(opt)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer Navigation */}
      <div
        style={{
          marginTop: "32px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <button className="secondary" onClick={onBack} style={{ gap: "6px" }}>
          <ArrowLeftIcon size={16} /> Back to Source Upload
        </button>

        <button
          className="primary"
          onClick={onNext}
          disabled={selectedIndices.length === 0}
          style={{ gap: "6px" }}
        >
          Proceed to Field Mapping ({selectedIndices.length} Questions) <ArrowRightIcon size={16} />
        </button>
      </div>
    </section>
  );
}
