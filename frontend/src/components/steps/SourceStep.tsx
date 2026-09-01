"use client";

import React, { useRef, useState } from "react";
import {
  SourceIcon,
  CheckIcon,
  CheckCircleIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
  FileTextIcon,
  XIcon,
  UploadIcon,
  AlertTriangleIcon,
} from "../icons";

export interface BatchFileItem {
  id: string;
  name: string;
  size: number;
  status: "pending" | "uploading" | "processing" | "success" | "error";
  progress: number;
  error?: string;
  absolute_path?: string;
  parent_source?: string | null;
}

interface SourceStepProps {
  files: BatchFileItem[];
  sourceData: {
    source_filename: string;
    source_type: string;
    questions: Record<string, any>[];
    statistics?: Record<string, any>;
    warning?: string | null;
  } | null;
  loading: boolean;
  extractionProgress: string;
  onAddFiles: (files: File[]) => void;
  onRemoveFile: (id: string) => void;
  onProcessBatch: () => void;
  onBack: () => void;
  onNext: () => void;
}

export default function SourceStep({
  files,
  sourceData,
  loading,
  extractionProgress,
  onAddFiles,
  onRemoveFile,
  onProcessBatch,
  onBack,
  onNext,
}: SourceStepProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files;
    if (selected && selected.length > 0) {
      onAddFiles(Array.from(selected));
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const dropped = e.dataTransfer.files;
    if (dropped && dropped.length > 0) {
      onAddFiles(Array.from(dropped));
    }
  };

  const getFileIcon = (filename: string) => {
    const ext = filename.split(".").pop()?.toLowerCase();
    if (ext === "zip") return "📦";
    if (ext === "pdf") return "📕";
    if (["docx", "doc"].includes(ext || "")) return "📘";
    if (["xlsx", "xls", "csv"].includes(ext || "")) return "📗";
    if (["png", "jpg", "jpeg", "webp"].includes(ext || "")) return "🖼️";
    return "📄";
  };

  const hasFilesToProcess = files.length > 0;
  const isAllUploaded = files.length > 0 && files.every((f) => f.status === "success" || f.status === "processing");
  const isAnyError = files.some((f) => f.status === "error");

  return (
    <section className="card">
      <div className="card-header-flex">
        <div>
          <div className="card-title">
            <SourceIcon size={22} color="var(--primary-hover)" /> Step 2: Source File Ingestion & Parsing
          </div>
          <div className="card-subtitle">
            Ingest assessment files. You can select multiple documents or drop ZIP archives to feed the extraction pipeline.
          </div>
        </div>
        <span className="badge info">Step 02 / 06</span>
      </div>

      {/* Drag and Drop Zone */}
      <div
        className={`file-upload-zone ${isDragOver ? "has-file" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        style={{
          borderStyle: isDragOver ? "solid" : "dashed",
          borderColor: isDragOver ? "var(--primary)" : "var(--border-medium)",
          background: isDragOver ? "rgba(59, 130, 246, 0.08)" : "rgba(14, 21, 36, 0.5)",
          padding: "40px 20px",
          textAlign: "center",
          cursor: "pointer",
          borderRadius: "12px",
          transition: "all 0.25s ease",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "12px"
        }}
      >
        <input
          type="file"
          ref={inputRef}
          accept=".pdf,.txt,.csv,.xlsx,.xls,.docx,.png,.jpg,.jpeg,.webp,.zip"
          multiple
          onChange={handleInputChange}
          style={{ display: "none" }}
        />
        <div style={{ padding: "12px", borderRadius: "50%", background: "rgba(59, 130, 246, 0.1)", color: "var(--primary-hover)" }}>
          <UploadIcon size={32} />
        </div>
        <strong style={{ fontSize: "0.95rem", color: "var(--text-primary)" }}>
          Drag & drop multiple files, ZIPs, or click to browse
        </strong>
        <span style={{ color: "var(--text-secondary)", fontSize: "0.82rem" }}>
          PDF, Word (.DOCX), Excel/CSV, ZIP archives, Text, and Scanned Images (PNG, JPG)
        </span>
      </div>

      {/* Multiple assessment warnings */}
      {sourceData?.warning && (
        <div
          style={{
            marginTop: "20px",
            background: "rgba(245, 158, 11, 0.08)",
            border: "1px solid rgba(245, 158, 11, 0.35)",
            color: "#FDE68A",
            padding: "16px",
            borderRadius: "8px",
            fontSize: "0.88rem",
            display: "flex",
            flexDirection: "column",
            gap: "10px"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 700 }}>
            <AlertTriangleIcon size={18} color="var(--warning)" /> Multiple Assessments Warning
          </div>
          <div>{sourceData.warning}</div>
          <div style={{ display: "flex", gap: "10px", marginTop: "4px" }}>
            <button
              className="accent"
              onClick={onNext}
              style={{ padding: "4px 12px", fontSize: "0.78rem" }}
            >
              Merge & Continue
            </button>
            <span style={{ fontSize: "0.78rem", color: "var(--text-secondary)", alignSelf: "center" }}>
              Or remove the conflicting file and re-extract.
            </span>
          </div>
        </div>
      )}

      {/* File Ingestion List */}
      {files.length > 0 && (
        <div style={{ marginTop: "24px" }}>
          <h4 style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "12px", fontWeight: 600 }}>
            Sources Queue ({files.length} File{files.length === 1 ? "" : "s"})
          </h4>
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {files.map((file) => (
              <div
                key={file.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "10px",
                  padding: "12px 16px",
                  position: "relative",
                  overflow: "hidden"
                }}
              >
                {/* Upload Progress Bar underlay */}
                {file.status === "uploading" && (
                  <div
                    style={{
                      position: "absolute",
                      left: 0,
                      top: 0,
                      bottom: 0,
                      background: "rgba(59, 130, 246, 0.08)",
                      width: `${file.progress}%`,
                      transition: "width 0.2s ease"
                    }}
                  />
                )}

                <div style={{ display: "flex", alignItems: "center", gap: "12px", zIndex: 2 }}>
                  <span style={{ fontSize: "1.4rem" }}>{getFileIcon(file.name)}</span>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: "0.9rem", color: "var(--text-primary)" }}>{file.name}</div>
                    <div style={{ fontSize: "0.76rem", color: "var(--text-secondary)" }}>
                      {formatFileSize(file.size)}
                      {file.parent_source && ` • Inside ${file.parent_source}`}
                    </div>
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "12px", zIndex: 2 }}>
                  {/* Status Badges */}
                  {file.status === "pending" && <span className="badge info">Pending</span>}
                  {file.status === "uploading" && (
                    <span className="badge info" style={{ gap: "4px" }}>
                      Uploading {file.progress}%
                    </span>
                  )}
                  {file.status === "processing" && (
                    <span className="badge info" style={{ gap: "4px" }}>
                      <span className="spinner" style={{ fontSize: "0.8rem" }}>⚙️</span> Processing
                    </span>
                  )}
                  {file.status === "success" && (
                    <span className="badge success" style={{ gap: "4px" }}>
                      <CheckIcon size={12} /> Ready
                    </span>
                  )}
                  {file.status === "error" && (
                    <span
                      className="badge danger"
                      title={file.error}
                      style={{ cursor: "help" }}
                    >
                      {file.error || "Failed"}
                    </span>
                  )}

                  {/* Remove Button */}
                  <button
                    className="secondary"
                    onClick={() => onRemoveFile(file.id)}
                    disabled={loading || file.status === "processing"}
                    style={{
                      padding: "6px",
                      borderRadius: "50%",
                      width: "30px",
                      height: "30px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      border: "none",
                      background: "rgba(255, 255, 255, 0.05)"
                    }}
                  >
                    <XIcon size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Extraction Process Logs */}
      {loading && (
        <div style={{ marginTop: "24px" }}>
          <div className="process-step-item active">
            <span className="spinner" style={{ fontSize: "1.1rem" }}>⚙️</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: "0.88rem", color: "var(--primary-hover)" }}>
                Parsing & Ingesting Combined Batch...
              </div>
              <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginTop: "2px" }}>
                {extractionProgress || "Extracting text nodes, OCR scanning, and isolating question blocks..."}
              </div>
            </div>
            <span className="badge info">IN PROGRESS</span>
          </div>
        </div>
      )}

      {/* Extraction Stats Summary */}
      {sourceData && !loading && (
        <div
          style={{
            marginTop: "24px",
            background: "rgba(0, 0, 0, 0.25)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "12px",
            padding: "20px"
          }}
        >
          <h4 style={{ fontSize: "0.88rem", color: "var(--accent)", marginBottom: "14px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            ✓ Extraction Complete
          </h4>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
              gap: "12px"
            }}
          >
            <div>
              <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>Questions Detected</div>
              <div style={{ fontSize: "1.35rem", fontWeight: 800, color: "var(--accent)" }}>
                {sourceData.questions.length} Items
              </div>
            </div>
            {sourceData.statistics?.matched !== undefined && (
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>Answers Matched</div>
                <div style={{ fontSize: "1.25rem", fontWeight: 800, color: "#93C5FD" }}>
                  {sourceData.statistics.matched} / {sourceData.statistics.total_questions_detected || sourceData.questions.length}
                </div>
              </div>
            )}
            {sourceData.statistics?.needs_review !== undefined && (
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>Needs Review</div>
                <div style={{ fontSize: "1.25rem", fontWeight: 800, color: sourceData.statistics.needs_review > 0 ? "var(--warning)" : "var(--accent)" }}>
                  {sourceData.statistics.needs_review} Items
                </div>
              </div>
            )}
            {sourceData.statistics?.duplicates !== undefined && (
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>Duplicates</div>
                <div style={{ fontSize: "1.25rem", fontWeight: 800, color: sourceData.statistics.duplicates > 0 ? "var(--warning)" : "var(--text-secondary)" }}>
                  {sourceData.statistics.duplicates} Items
                </div>
              </div>
            )}
            {sourceData.statistics?.pages_processed && (
              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>Pages Processed</div>
                <div style={{ fontSize: "1.25rem", fontWeight: 800, color: "#C4B5FD" }}>
                  {sourceData.statistics.pages_processed} Pages
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Footer Navigation */}
      <div
        style={{
          marginTop: "32px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center"
        }}
      >
        <button className="secondary" onClick={onBack} style={{ gap: "6px" }} disabled={loading}>
          <ArrowLeftIcon size={16} /> Back to Templates
        </button>

        <div style={{ display: "flex", gap: "12px" }}>
          {hasFilesToProcess && !sourceData && (
            <button
              className="accent"
              onClick={onProcessBatch}
              disabled={loading || isAnyError}
              style={{ gap: "6px" }}
            >
              {loading ? "Processing..." : "Start Ingestion & Parsing"} <ArrowRightIcon size={16} />
            </button>
          )}

          {sourceData && (
            <button
              className="primary"
              onClick={onNext}
              disabled={loading}
              style={{ gap: "6px" }}
            >
              Proceed to Question Selection <ArrowRightIcon size={16} />
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
