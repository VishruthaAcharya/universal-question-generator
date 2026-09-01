"use client";

import React, { useState } from "react";
import AlertPanel from "../AlertPanel";
import { AssessmentBatchConfig } from "../../types";
import {
  ExportIcon,
  CheckCircleIcon,
  AlertTriangleIcon,
  ArrowLeftIcon,
  FileTextIcon,
  SparklesIcon,
} from "../icons";

interface ExportStepProps {
  batchConfig: AssessmentBatchConfig;
  templateName: string;
  totalQuestions: number;
  hasValidationErrors: boolean;
  loading: boolean;
  onExport: (format: "csv" | "xlsx", isDraft?: boolean) => Promise<void> | void;
  onBack: () => void;
}

export default function ExportStep({
  batchConfig,
  templateName,
  totalQuestions,
  hasValidationErrors,
  loading,
  onExport,
  onBack,
}: ExportStepProps) {
  const [downloadSuccess, setDownloadSuccess] = useState<string | null>(null);

  const handleDownload = async (format: "csv" | "xlsx", isDraft: boolean = false) => {
    try {
      await onExport(format, isDraft);
      setDownloadSuccess(isDraft ? `Draft ${format.toUpperCase()}` : `Certified ${format.toUpperCase()}`);
    } catch (e) {
      // Error handled in parent
    }
  };

  return (
    <section className="card">
      <div className="card-header-flex">
        <div>
          <div className="card-title">
            <ExportIcon size={22} color="var(--primary-hover)" /> Step 6: Export & Publishing
          </div>
          <div className="card-subtitle">
            Export the reviewed and validated assessment items formatted strictly according to the Menntr target schema.
          </div>
        </div>
        <span className="badge info">Step 06 / 06</span>
      </div>

      <div
        style={{
          background: "var(--bg-surface)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "14px",
          padding: "32px 24px",
          textAlign: "center",
          marginBottom: "28px",
        }}
      >
        <div style={{ display: "inline-flex", padding: "16px", borderRadius: "50%", background: "rgba(59, 130, 246, 0.1)", marginBottom: "16px" }}>
          <FileTextIcon size={40} color="var(--primary-hover)" />
        </div>

        <h2 style={{ fontSize: "1.45rem", fontWeight: 800, marginBottom: "8px" }}>
          {batchConfig.assessmentName || "Menntr Assessment Batch"}
        </h2>

        <p style={{ color: "var(--text-secondary)", fontSize: "0.88rem", maxWidth: "560px", margin: "0 auto 24px auto", lineHeight: "1.5" }}>
          Ready for delivery. Output preserves target template headers, column ordering, and data structures with internal database fields omitted.
        </p>

        {/* Batch Summary Chips */}
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            gap: "12px",
            flexWrap: "wrap",
            marginBottom: "28px",
          }}
        >
          <div className="topbar-meta-chip">
            Subject: <strong>{batchConfig.subject || "General"}</strong>
          </div>
          <div className="topbar-meta-chip">
            Grade: <strong>{batchConfig.gradeClass || "Class 10"}</strong>
          </div>
          <div className="topbar-meta-chip">
            Questions: <strong>{totalQuestions} Selected & Validated</strong>
          </div>
          <div className="topbar-meta-chip">
            Schema: <strong>{templateName || "Menntr Schema"}</strong>
          </div>
        </div>

        {hasValidationErrors && (
          <AlertPanel
            type="warning"
            style={{ maxWidth: "600px", margin: "0 auto 24px auto", textAlign: "left" }}
          >
            <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
              <AlertTriangleIcon size={16} /> <strong>Notice:</strong> Some questions contain non-blocking warnings. You may export a certified delivery file or download a draft export for offline inspection.
            </span>
          </AlertPanel>
        )}

        {downloadSuccess && (
          <AlertPanel
            type="success"
            style={{ maxWidth: "600px", margin: "0 auto 24px auto" }}
          >
            <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
              <CheckCircleIcon size={16} /> <strong>{downloadSuccess} Export Generated!</strong> Your file has downloaded successfully.
            </span>
          </AlertPanel>
        )}

        {/* Certified Export Buttons */}
        <div style={{ marginBottom: "20px" }}>
          <div style={{ fontSize: "0.82rem", fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase", marginBottom: "12px" }}>
            Certified Production Export
          </div>
          <div style={{ display: "flex", gap: "16px", justifyContent: "center", flexWrap: "wrap" }}>
            <button
              className="primary"
              onClick={() => handleDownload("xlsx", false)}
              disabled={loading}
              style={{ padding: "12px 28px", fontSize: "0.92rem", gap: "8px" }}
            >
              {loading ? (
                <>
                  <span className="spinner">⚙️</span> Generating Excel...
                </>
              ) : (
                <>
                  <ExportIcon size={16} /> Download Certified Excel (.XLSX)
                </>
              )}
            </button>

            <button
              className="accent"
              onClick={() => handleDownload("csv", false)}
              disabled={loading}
              style={{ padding: "12px 28px", fontSize: "0.92rem", gap: "8px" }}
            >
              {loading ? (
                <>
                  <span className="spinner">⚙️</span> Generating CSV...
                </>
              ) : (
                <>
                  <ExportIcon size={16} /> Download Certified CSV (.CSV)
                </>
              )}
            </button>
          </div>
        </div>

        {/* Draft / Review Export Section */}
        <div
          style={{
            marginTop: "24px",
            paddingTop: "20px",
            borderTop: "1px solid var(--border-subtle)",
            maxWidth: "600px",
            margin: "24px auto 0 auto",
          }}
        >
          <div style={{ fontSize: "0.80rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "8px" }}>
            Draft / Inspection Export (Preserves MISSING & AI_INFERRED provenance states)
          </div>
          <div style={{ display: "flex", gap: "12px", justifyContent: "center", flexWrap: "wrap" }}>
            <button
              className="secondary"
              onClick={() => handleDownload("xlsx", true)}
              disabled={loading}
              style={{
                padding: "8px 18px",
                fontSize: "0.82rem",
                gap: "6px",
                background: "rgba(255, 255, 255, 0.06)",
                border: "1px solid rgba(255, 255, 255, 0.18)",
              }}
            >
              <FileTextIcon size={14} /> Download Draft / Review (.XLSX)
            </button>

            <button
              className="secondary"
              onClick={() => handleDownload("csv", true)}
              disabled={loading}
              style={{
                padding: "8px 18px",
                fontSize: "0.82rem",
                gap: "6px",
                background: "rgba(255, 255, 255, 0.06)",
                border: "1px solid rgba(255, 255, 255, 0.18)",
              }}
            >
              <FileTextIcon size={14} /> Download Draft / Review (.CSV)
            </button>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <div
        style={{
          marginTop: "32px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <button className="secondary" onClick={onBack} style={{ gap: "6px" }}>
          <ArrowLeftIcon size={16} /> Back to Quality Dashboard
        </button>

        <span style={{ fontSize: "0.76rem", color: "var(--text-muted)" }}>
          Menntr AI Assessment Content Factory • Quality Verified
        </span>
      </div>
    </section>
  );
}
