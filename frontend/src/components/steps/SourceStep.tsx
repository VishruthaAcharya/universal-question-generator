"use client";

import React from "react";
import FileUploadZone from "../FileUploadZone";
import {
  SourceIcon,
  CheckIcon,
  CheckCircleIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
  FileTextIcon,
} from "../icons";

interface SourceStepProps {
  sourceFile: File | null;
  sourceData: {
    source_filename: string;
    source_type: string;
    questions: Record<string, any>[];
  } | null;
  loading: boolean;
  extractionProgress: string;
  onSourceChange: (file: File) => void;
  onBack: () => void;
  onNext: () => void;
}

export default function SourceStep({
  sourceFile,
  sourceData,
  loading,
  extractionProgress,
  onSourceChange,
  onBack,
  onNext,
}: SourceStepProps) {
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  return (
    <section className="card">
      <div className="card-header-flex">
        <div>
          <div className="card-title">
            <SourceIcon size={22} color="var(--primary-hover)" /> Step 2: Source File Ingestion & Parsing
          </div>
          <div className="card-subtitle">
            Upload assessment source files. The extraction engine processes all pages and yields 100% of detected questions.
          </div>
        </div>
        <span className="badge info">Step 02 / 08</span>
      </div>

      <FileUploadZone
        file={sourceFile}
        accept=".pdf,.txt,.csv,.xlsx,.xls,.docx,.png,.jpg,.jpeg,.webp"
        onFileChange={onSourceChange}
        title="Drag & drop assessment source files or click to browse"
        supportedFormatsText="Enterprise formats supported: PDF, Word (.DOCX), Excel/CSV, Text, and Scanned High-Res Images"
        successBadgeText="Source Ingested"
      />

      {loading && (
        <div style={{ marginTop: "24px" }}>
          <div className="process-step-item active">
            <span className="spinner" style={{ fontSize: "1.1rem" }}>⚙️</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: "0.88rem", color: "var(--primary-hover)" }}>
                Parsing & Ingesting Complete Document...
              </div>
              <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginTop: "2px" }}>
                {extractionProgress || "Extracting text nodes, OCR scanning, and isolating 100% of question blocks..."}
              </div>
            </div>
            <span className="badge info">IN PROGRESS</span>
          </div>
        </div>
      )}

      {sourceFile && (
        <div
          style={{
            marginTop: "24px",
            background: "var(--bg-surface)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "12px",
            padding: "20px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <FileTextIcon size={22} color="var(--primary-hover)" />
              <div>
                <div style={{ fontWeight: 700, fontSize: "0.95rem" }}>{sourceFile.name}</div>
                <div style={{ fontSize: "0.76rem", color: "var(--text-secondary)" }}>
                  {formatFileSize(sourceFile.size)} • Type: {sourceFile.name.split(".").pop()?.toUpperCase() || "UNKNOWN"}
                </div>
              </div>
            </div>
            <span className={`badge ${sourceData ? "success" : loading ? "info" : "warning"}`} style={{ gap: "4px" }}>
              {sourceData ? (
                <>
                  <CheckIcon size={12} /> {sourceData.questions.length} Questions Extracted
                </>
              ) : loading ? (
                "Extracting"
              ) : (
                "Uploaded"
              )}
            </span>
          </div>

          {sourceData && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                gap: "12px",
                background: "rgba(0, 0, 0, 0.25)",
                borderRadius: "8px",
                padding: "14px",
              }}
            >
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>Questions Extracted</div>
                <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "var(--accent)" }}>
                  {sourceData.questions.length} Questions
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>Extraction Engine</div>
                <div style={{ fontSize: "1.25rem", fontWeight: 800, color: "#93C5FD" }}>
                  {sourceData.source_type.toUpperCase()} Parser
                </div>
              </div>
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>Status</div>
                <div style={{ fontSize: "1.25rem", fontWeight: 800, color: "var(--accent)", display: "flex", alignItems: "center", gap: "6px" }}>
                  <CheckCircleIcon size={18} /> COMPLETE
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      <div
        style={{
          marginTop: "32px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <button className="secondary" onClick={onBack} style={{ gap: "6px" }}>
          <ArrowLeftIcon size={16} /> Back to Templates
        </button>

        <button
          className="primary"
          onClick={onNext}
          disabled={!sourceData || loading}
          style={{ gap: "6px" }}
        >
          {loading ? "Extracting..." : "Proceed to Question Selection"} <ArrowRightIcon size={16} />
        </button>
      </div>
    </section>
  );
}
