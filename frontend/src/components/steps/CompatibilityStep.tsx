"use client";

import React from "react";
import type { CompatibilityReport, TemplateSchema } from "../../types";
import {
  MappingIcon,
  CheckIcon,
  CheckCircleIcon,
  AlertTriangleIcon,
  XCircleIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
  SparklesIcon,
} from "../icons";

interface CompatibilityStepProps {
  compatibility: CompatibilityReport;
  templateSchema: TemplateSchema | null;
  selectedQuestionsCount: number;
  loading: boolean;
  onBack: () => void;
  onChangeTemplate: () => void;
  onProceedToMapping: () => void;
}

export default function CompatibilityStep({
  compatibility,
  templateSchema,
  selectedQuestionsCount,
  loading,
  onBack,
  onChangeTemplate,
  onProceedToMapping,
}: CompatibilityStepProps) {
  const columns = templateSchema?.column_schema || [];
  const missingRequired = compatibility.errors.map((e) => e.field);
  const inferrableOrWarning = compatibility.warnings.map((w) => w.field);

  // Calculate compatibility percentage
  const totalCols = columns.length || 1;
  const matchedCols = columns.filter(
    (c) => !missingRequired.includes(c.original_name) && !inferrableOrWarning.includes(c.original_name)
  ).length;
  const inferrableCols = columns.filter((c) => inferrableOrWarning.includes(c.original_name)).length;
  const compatibilityScore = Math.round(((matchedCols + inferrableCols * 0.8) / totalCols) * 100);

  return (
    <section className="card">
      <div className="card-header-flex">
        <div>
          <div className="card-title">
            <MappingIcon size={22} color="var(--primary-hover)" /> Step 4: Schema Field Mapping & Compatibility
          </div>
          <div className="card-subtitle">
            Understand how extracted source fields map to target Menntr schema fields for the <strong>{selectedQuestionsCount} selected questions</strong>.
          </div>
        </div>
        <span className="badge info">Step 04 / 08</span>
      </div>

      {/* Compatibility Overview Bar */}
      <div
        style={{
          background: "var(--bg-surface)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "14px",
          padding: "20px 24px",
          marginBottom: "24px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div
            style={{
              width: "52px",
              height: "52px",
              borderRadius: "12px",
              background: compatibilityScore >= 80 ? "rgba(16, 185, 129, 0.15)" : "rgba(245, 158, 11, 0.15)",
              border: `1px solid ${compatibilityScore >= 80 ? "var(--accent)" : "var(--warning)"}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: 800,
              fontSize: "1.2rem",
              color: compatibilityScore >= 80 ? "var(--accent)" : "var(--warning)",
            }}
          >
            {compatibilityScore}%
          </div>

          <div>
            <div style={{ fontWeight: 700, fontSize: "1.05rem", color: "var(--text-primary)", display: "flex", alignItems: "center", gap: "6px" }}>
              {compatibility.compatible ? (
                <>
                  <CheckCircleIcon size={18} color="var(--accent)" /> Target Schema Compatible with Source
                </>
              ) : (
                <>
                  <AlertTriangleIcon size={18} color="var(--warning)" /> Schema Discrepancy Detected
                </>
              )}
            </div>
            <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginTop: "2px" }}>
              {matchedCols} direct matches • {inferrableCols} AI-inferable fields • {missingRequired.length} unmapped required
            </div>
          </div>
        </div>

        {/* Informational notice that AI Fill is available in Human Review */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", background: "rgba(59, 130, 246, 0.1)", border: "1px solid rgba(59, 130, 246, 0.25)", padding: "8px 14px", borderRadius: "8px", fontSize: "0.8rem", color: "#BFDBFE" }}>
          <SparklesIcon size={16} color="#93C5FD" />
          <span>Missing AI-inferable fields can be completed during Human Review.</span>
        </div>
      </div>

      {/* Field Mapping Matrix Table */}
      <div style={{ marginTop: "16px" }}>
        <div style={{ fontWeight: 700, fontSize: "0.95rem", marginBottom: "12px" }}>
          Target Schema Field Taxonomy & Origin Matrix
        </div>

        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th style={{ width: "220px" }}>Menntr Target Field</th>
                <th style={{ width: "140px" }}>Field Origin</th>
                <th style={{ width: "120px" }}>Requirement</th>
                <th>Resolution Status & AI Capability</th>
              </tr>
            </thead>
            <tbody>
              {columns.map((col, idx) => {
                const isMissingReq = missingRequired.includes(col.original_name);
                const isWarning = inferrableOrWarning.includes(col.original_name);

                let originLabel = "EXTRACTED";
                let badgeClass = "success";
                let resolutionText = "Verbatim extraction from source document";

                if (isMissingReq) {
                  originLabel = "MISSING";
                  badgeClass = "danger";
                  resolutionText = "Mandatory in schema but missing in source (requires source fix or manual entry)";
                } else if (isWarning) {
                  originLabel = "AI_INFERABLE";
                  badgeClass = "warning";
                  resolutionText = "AI infers topic, difficulty, or metadata during Human Review";
                }

                return (
                  <tr key={idx}>
                    <td>
                      <strong style={{ color: "var(--text-primary)" }}>{col.original_name}</strong>
                    </td>
                    <td>
                      <span className={`badge ${badgeClass}`}>{originLabel}</span>
                    </td>
                    <td>
                      {col.required ? (
                        <span className="badge danger">Required</span>
                      ) : (
                        <span className="badge info">Optional</span>
                      )}
                    </td>
                    <td style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                      {resolutionText}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Navigation */}
      <div
        style={{
          marginTop: "36px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <button className="secondary" onClick={onBack} style={{ gap: "6px" }}>
          <ArrowLeftIcon size={16} /> Back to Question Selection
        </button>

        <div style={{ display: "flex", gap: "12px" }}>
          {!compatibility.compatible && missingRequired.length > 0 && (
            <button className="secondary" onClick={onChangeTemplate}>
              Select Different Template
            </button>
          )}

          <button
            className="primary"
            onClick={onProceedToMapping}
            disabled={loading}
            style={{ gap: "6px" }}
          >
            {loading ? (
              <>
                <span className="spinner">⚙️</span> Normalizing & Mapping Questions...
              </>
            ) : (
              <>
                Execute Mapping & Proceed to AI Validation <ArrowRightIcon size={16} />
              </>
            )}
          </button>
        </div>
      </div>
    </section>
  );
}
