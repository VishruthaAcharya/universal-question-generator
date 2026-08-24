"use client";

import React, { useState, useEffect } from "react";
import type { TemplateSchema, SavedTemplate, TemplateUploadResult } from "../../types";
import { listSavedTemplates, deleteSavedTemplate, uploadTemplate } from "../../lib/api";
import FileUploadZone from "../FileUploadZone";
import AlertPanel from "../AlertPanel";
import {
  TemplateIcon,
  EyeIcon,
  TrashIcon,
  CheckIcon,
  XIcon,
  UploadIcon,
  CheckCircleIcon,
  AlertTriangleIcon,
  ArrowRightIcon,
} from "../icons";

interface TemplateStepProps {
  templateFile: File | null;
  templateId: string;
  templateSchema: TemplateSchema | null;
  onTemplateSelected: (templateId: string, templateName: string, schema: TemplateSchema) => void;
  onNext: () => void;
}

export default function TemplateStep({
  templateFile,
  templateId,
  templateSchema,
  onTemplateSelected,
  onNext,
}: TemplateStepProps) {
  const [tab, setTab] = useState<"registry" | "upload">("registry");
  const [savedTemplates, setSavedTemplates] = useState<SavedTemplate[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [previewTemplate, setPreviewTemplate] = useState<SavedTemplate | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SavedTemplate | null>(null);
  const [duplicateNotice, setDuplicateNotice] = useState<TemplateUploadResult | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [isUploading, setIsUploading] = useState(false);

  const defaultTemplates: SavedTemplate[] = [
    {
      id: "tpl-default-mcq-1",
      name: "Menntr MCQ Standard V1",
      original_filename: "menntr_mcq_standard_v1.xlsx",
      sheet_name: "Assessment",
      created_at: "2026-08-01T10:00:00Z",
      usage_count: 14,
      is_archived: false,
      schema: {
        original_filename: "menntr_mcq_standard_v1.xlsx",
        sheet_name: "Assessment",
        columns: ["Question", "Option A", "Option B", "Option C", "Option D", "Correct Answer", "Topic", "Difficulty", "Bloom's Taxonomy", "Score"],
        column_schema: [
          { original_name: "Question", normalized_name: "question", required: true, example_value: "Solve x^2 - 5x + 6 = 0" },
          { original_name: "Option A", normalized_name: "option_1", required: true, example_value: "x = 2, 3" },
          { original_name: "Option B", normalized_name: "option_2", required: true, example_value: "x = -2, -3" },
          { original_name: "Option C", normalized_name: "option_3", required: true, example_value: "x = 1, 6" },
          { original_name: "Option D", normalized_name: "option_4", required: true, example_value: "x = -1, -6" },
          { original_name: "Correct Answer", normalized_name: "correct_answer", required: true, example_value: "A" },
          { original_name: "Topic", normalized_name: "topic", required: false, example_value: "Quadratic Equations" },
          { original_name: "Difficulty", normalized_name: "difficulty", required: false, example_value: "Medium" },
          { original_name: "Bloom's Taxonomy", normalized_name: "blooms_taxonomy", required: false, example_value: "Application" },
          { original_name: "Score", normalized_name: "score", required: false, example_value: "1" },
        ],
        has_examples: true,
      },
    },
    {
      id: "tpl-default-physics-2",
      name: "Physics Assessment Standard V2",
      original_filename: "physics_assessment_v2.xlsx",
      sheet_name: "Questions",
      created_at: "2026-08-10T14:30:00Z",
      usage_count: 8,
      is_archived: false,
      schema: {
        original_filename: "physics_assessment_v2.xlsx",
        sheet_name: "Questions",
        columns: ["Item Prompt", "Choice 1", "Choice 2", "Choice 3", "Choice 4", "Answer Key", "Subtopic", "Difficulty Level", "Time Limit (s)"],
        column_schema: [
          { original_name: "Item Prompt", normalized_name: "question", required: true, example_value: "State Coulomb's Law formula." },
          { original_name: "Choice 1", normalized_name: "option_1", required: true, example_value: "F = k*q1*q2/r^2" },
          { original_name: "Choice 2", normalized_name: "option_2", required: true, example_value: "F = m*a" },
          { original_name: "Choice 3", normalized_name: "option_3", required: true, example_value: "E = m*c^2" },
          { original_name: "Choice 4", normalized_name: "option_4", required: true, example_value: "V = I*R" },
          { original_name: "Answer Key", normalized_name: "correct_answer", required: true, example_value: "1" },
          { original_name: "Subtopic", normalized_name: "subtopic", required: false, example_value: "Electrostatics" },
          { original_name: "Difficulty Level", normalized_name: "difficulty", required: false, example_value: "Medium" },
          { original_name: "Time Limit (s)", normalized_name: "time_limit", required: false, example_value: "60" },
        ],
        has_examples: true,
      },
    },
  ];

  const fetchTemplates = async () => {
    setLoadingTemplates(true);
    try {
      const list = await listSavedTemplates(false);
      // Merge unique
      const merged = [...list];
      defaultTemplates.forEach((def) => {
        if (!merged.some((t) => t.name === def.name || t.id === def.id)) {
          merged.push(def);
        }
      });
      setSavedTemplates(merged);
      if (merged.length === 0) setTab("upload");
    } catch (e) {
      console.error("Failed to load templates:", e);
    } finally {
      setLoadingTemplates(false);
    }
  };

  useEffect(() => {
    fetchTemplates();
  }, []);

  const handleFileUpload = async (file: File) => {
    setIsUploading(true);
    setDuplicateNotice(null);
    setErrorMessage("");
    setStatusMessage("");
    try {
      const res = await uploadTemplate(file);
      if (res.is_duplicate) {
        setDuplicateNotice(res);
      } else {
        setStatusMessage(`Template "${res.name}" added to library.`);
        onTemplateSelected(res.template_id, res.name, res.schema);
        await fetchTemplates();
        setTab("registry");
      }
    } catch (e) {
      setErrorMessage(e instanceof Error ? e.message : "Failed to upload template");
    } finally {
      setIsUploading(false);
    }
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      if (deleteTarget.id.startsWith("tpl-default-")) {
        setSavedTemplates((prev) => prev.filter((t) => t.id !== deleteTarget.id));
        setStatusMessage(`Template "${deleteTarget.name}" removed.`);
      } else {
        const res = await deleteSavedTemplate(deleteTarget.id);
        setStatusMessage(res.message || `Template "${deleteTarget.name}" removed.`);
        await fetchTemplates();
      }
      setDeleteTarget(null);
    } catch (e) {
      setErrorMessage(e instanceof Error ? e.message : "Failed to remove template");
    }
  };

  return (
    <section className="card">
      <div className="card-header-flex">
        <div>
          <div className="card-title">
            <TemplateIcon size={22} color="var(--primary-hover)" /> Step 1: Menntr Assessment Schema & Template Registry
          </div>
          <div className="card-subtitle">
            Select an enterprise saved schema from your reusable library or upload a custom Excel / CSV template defining the target assessment structure.
          </div>
        </div>
        <span className="badge info">Step 01 / 08</span>
      </div>

      {statusMessage && (
        <AlertPanel type="success" style={{ marginBottom: "16px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
              <CheckCircleIcon size={16} /> {statusMessage}
            </span>
            <button className="secondary" onClick={() => setStatusMessage("")} style={{ padding: "2px 6px", fontSize: "0.7rem" }}>
              ✕
            </button>
          </div>
        </AlertPanel>
      )}

      {errorMessage && (
        <AlertPanel type="danger" style={{ marginBottom: "16px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
              <AlertTriangleIcon size={16} /> {errorMessage}
            </span>
            <button className="secondary" onClick={() => setErrorMessage("")} style={{ padding: "2px 6px", fontSize: "0.7rem" }}>
              ✕
            </button>
          </div>
        </AlertPanel>
      )}

      {/* Duplicate Template Notice */}
      {duplicateNotice && (
        <AlertPanel type="warning" style={{ marginBottom: "20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
            <div>
              <strong>Template already exists in your library:</strong>
              <div style={{ fontSize: "0.85rem", color: "var(--text-primary)", marginTop: "2px" }}>
                "{duplicateNotice.name}" ({duplicateNotice.schema.columns.length} columns)
              </div>
            </div>

            <div style={{ display: "flex", gap: "8px" }}>
              <button
                className="accent"
                onClick={() => {
                  onTemplateSelected(duplicateNotice.template_id, duplicateNotice.name, duplicateNotice.schema);
                  setDuplicateNotice(null);
                  setTab("registry");
                }}
                style={{ padding: "6px 14px", fontSize: "0.8rem" }}
              >
                Use Existing Template
              </button>
              <button
                className="secondary"
                onClick={() => setDuplicateNotice(null)}
                style={{ padding: "6px 10px", fontSize: "0.8rem" }}
              >
                Dismiss
              </button>
            </div>
          </div>
        </AlertPanel>
      )}

      {/* Tab Navigation */}
      <div style={{ display: "flex", gap: "10px", marginBottom: "24px" }}>
        <button
          className={tab === "registry" ? "primary" : "secondary"}
          onClick={() => setTab("registry")}
          style={{ padding: "8px 18px", fontSize: "0.86rem", gap: "6px" }}
        >
          <TemplateIcon size={16} /> Saved Templates ({savedTemplates.length})
        </button>
        <button
          className={tab === "upload" ? "primary" : "secondary"}
          onClick={() => setTab("upload")}
          style={{ padding: "8px 18px", fontSize: "0.86rem", gap: "6px" }}
        >
          <UploadIcon size={16} /> Upload New Template
        </button>
      </div>

      {/* TAB 1: SAVED TEMPLATES REGISTRY */}
      {tab === "registry" && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "16px" }}>
            {savedTemplates.map((tpl) => {
              const isSelected = templateId === tpl.id || (templateSchema && templateSchema.original_filename === tpl.original_filename);
              const requiredCount = tpl.schema.column_schema.filter((c) => c.required).length;
              const optionalCount = tpl.schema.column_schema.length - requiredCount;

              return (
                <div
                  key={tpl.id}
                  style={{
                    background: isSelected ? "rgba(59, 130, 246, 0.12)" : "var(--bg-surface)",
                    border: `1px solid ${isSelected ? "var(--primary)" : "var(--border-subtle)"}`,
                    borderRadius: "12px",
                    padding: "20px",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    gap: "14px",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "6px" }}>
                      <div style={{ fontWeight: 700, fontSize: "0.98rem", color: "var(--text-primary)" }}>
                        {tpl.name}
                      </div>
                      {isSelected && (
                        <span className="badge success" style={{ gap: "4px" }}>
                          <CheckIcon size={12} /> Active
                        </span>
                      )}
                    </div>

                    <div style={{ fontSize: "0.76rem", color: "var(--text-muted)", marginBottom: "12px" }}>
                      {tpl.original_filename} {tpl.sheet_name ? `• Sheet: ${tpl.sheet_name}` : ""}
                    </div>

                    <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "8px" }}>
                      <span className="badge info">{tpl.schema.columns.length} Fields</span>
                      <span className="badge danger">{requiredCount} Required</span>
                      <span className="badge warning">{optionalCount} Optional</span>
                    </div>

                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "4px" }}>
                      Used in {tpl.usage_count || 0} assessment(s)
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: "8px", borderTop: "1px solid var(--border-subtle)", paddingTop: "14px" }}>
                    <button
                      className={isSelected ? "accent" : "primary"}
                      onClick={() => onTemplateSelected(tpl.id, tpl.name, tpl.schema)}
                      style={{ flex: 1, padding: "7px 12px", fontSize: "0.82rem" }}
                    >
                      {isSelected ? "Selected" : "Use Template"}
                    </button>
                    <button
                      className="secondary"
                      onClick={() => setPreviewTemplate(tpl)}
                      style={{ padding: "7px 10px", fontSize: "0.82rem" }}
                      title="View Schema Structure"
                    >
                      <EyeIcon size={14} />
                    </button>
                    <button
                      className="secondary"
                      onClick={() => setDeleteTarget(tpl)}
                      style={{ padding: "7px 10px", fontSize: "0.82rem", color: "var(--danger)" }}
                      title="Delete / Archive Template"
                    >
                      <TrashIcon size={14} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* TAB 2: UPLOAD NEW TEMPLATE */}
      {tab === "upload" && (
        <div>
          <FileUploadZone
            file={templateFile}
            accept=".csv,.xlsx,.xls"
            onFileChange={handleFileUpload}
            title="Upload New Menntr Target Assessment Schema (XLSX / CSV)"
            supportedFormatsText="Automatically parses headers, required columns, and saves to template registry"
            successBadgeText="Schema Loaded"
          />
        </div>
      )}

      {/* ACTIVE SCHEMA DETAILS */}
      {templateSchema && (
        <div style={{ marginTop: "32px", borderTop: "1px solid var(--border-subtle)", paddingTop: "24px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px", flexWrap: "wrap", gap: "10px" }}>
            <div>
              <h3 style={{ margin: 0, fontSize: "1.05rem", fontWeight: 700 }}>
                Active Schema: {templateSchema.original_filename} ({templateSchema.columns.length} Fields)
              </h3>
              <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginTop: "2px" }}>
                Target output structure is locked and ready for question extraction and mapping.
              </div>
            </div>
            {templateSchema.sheet_name && (
              <span className="badge info">Worksheet: {templateSchema.sheet_name}</span>
            )}
          </div>

          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th style={{ width: "220px" }}>Schema Field</th>
                  <th style={{ width: "180px" }}>Canonical Mapping</th>
                  <th style={{ width: "120px" }}>Requirement</th>
                  <th>Example Target Value</th>
                </tr>
              </thead>
              <tbody>
                {templateSchema.column_schema.map((c, i) => (
                  <tr key={i}>
                    <td>
                      <strong style={{ color: "var(--text-primary)" }}>{c.original_name}</strong>
                    </td>
                    <td>
                      <span className={`badge ${c.original_name === c.normalized_name ? "info" : "purple"}`}>
                        {c.normalized_name}
                      </span>
                    </td>
                    <td>
                      {c.required ? (
                        <span className="badge danger">Required</span>
                      ) : (
                        <span className="badge info">Optional</span>
                      )}
                    </td>
                    <td style={{ color: "var(--text-secondary)", fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}>
                      {c.example_value || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ marginTop: "28px", display: "flex", justifyContent: "flex-end" }}>
            <button className="primary" onClick={onNext} style={{ minWidth: "220px", gap: "6px" }}>
              Proceed to Source Files <ArrowRightIcon size={16} />
            </button>
          </div>
        </div>
      )}

      {/* SCHEMA PREVIEW MODAL */}
      {previewTemplate && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.75)",
            backdropFilter: "blur(6px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "var(--bg-card-solid)",
              border: "1px solid var(--border-medium)",
              borderRadius: "16px",
              padding: "28px",
              maxWidth: "750px",
              width: "100%",
              maxHeight: "85vh",
              overflowY: "auto",
              boxShadow: "0 20px 40px rgba(0,0,0,0.5)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <div>
                <h3 style={{ margin: 0, fontWeight: 700 }}>{previewTemplate.name}</h3>
                <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginTop: "2px" }}>
                  {previewTemplate.original_filename} • {previewTemplate.schema.columns.length} columns
                </div>
              </div>
              <button className="secondary" onClick={() => setPreviewTemplate(null)} style={{ padding: "4px 8px" }}>
                <XIcon size={16} />
              </button>
            </div>

            <div className="table-wrapper" style={{ maxHeight: "400px" }}>
              <table>
                <thead>
                  <tr>
                    <th>Column Name</th>
                    <th>Normalized Key</th>
                    <th>Requirement</th>
                  </tr>
                </thead>
                <tbody>
                  {previewTemplate.schema.column_schema.map((c, idx) => (
                    <tr key={idx}>
                      <td><strong>{c.original_name}</strong></td>
                      <td><span className="badge info">{c.normalized_name}</span></td>
                      <td>
                        {c.required ? <span className="badge danger">Required</span> : <span className="badge info">Optional</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px", marginTop: "20px" }}>
              <button className="secondary" onClick={() => setPreviewTemplate(null)}>
                Close
              </button>
              <button
                className="primary"
                onClick={() => {
                  onTemplateSelected(previewTemplate.id, previewTemplate.name, previewTemplate.schema);
                  setPreviewTemplate(null);
                }}
              >
                Use This Template
              </button>
            </div>
          </div>
        </div>
      )}

      {/* DELETE CONFIRMATION DIALOG */}
      {deleteTarget && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.75)",
            backdropFilter: "blur(6px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "var(--bg-card-solid)",
              border: "1px solid var(--border-medium)",
              borderRadius: "16px",
              padding: "28px",
              maxWidth: "480px",
              width: "100%",
              boxShadow: "0 20px 40px rgba(0,0,0,0.5)",
            }}
          >
            <h3 style={{ margin: "0 0 8px 0", color: "var(--text-primary)" }}>Delete Template?</h3>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.88rem", lineHeight: "1.5", marginBottom: "24px" }}>
              Are you sure you want to remove <strong>"{deleteTarget.name}"</strong> from your template library? If it is referenced by existing assessment batches, it will be safely archived.
            </p>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px" }}>
              <button className="secondary" onClick={() => setDeleteTarget(null)}>
                Cancel
              </button>
              <button className="danger-btn" onClick={handleConfirmDelete}>
                Delete Template
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
