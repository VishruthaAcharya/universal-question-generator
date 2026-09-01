"use client";

import React, { useState } from "react";
import { FactoryStepKey, AssessmentBatchConfig } from "../types";
import {
  TemplateIcon,
  SourceIcon,
  SelectionIcon,
  MappingIcon,
  ValidationIcon,
  ReviewIcon,
  QualityIcon,
  ExportIcon,
  EditIcon,
  CheckIcon,
  XIcon,
  CheckCircleIcon,
  AlertTriangleIcon,
  AlertCircleIcon,
  XCircleIcon,
  ArrowRightIcon,
} from "./icons";

interface NavItemDef {
  key: FactoryStepKey;
  label: string;
  icon: React.ReactNode;
  stepNum: string;
  section: string;
}

const NAV_ITEMS: NavItemDef[] = [
  { key: "templates", label: "Templates", icon: <TemplateIcon size={18} />, stepNum: "01", section: "Pipeline" },
  { key: "source", label: "Upload Sources", icon: <SourceIcon size={18} />, stepNum: "02", section: "Pipeline" },
  { key: "selection", label: "Questions", icon: <SelectionIcon size={18} />, stepNum: "03", section: "Pipeline" },
  { key: "review", label: "Review", icon: <ReviewIcon size={18} />, stepNum: "04", section: "Pipeline" },
  { key: "quality", label: "Quality Check", icon: <QualityIcon size={18} />, stepNum: "05", section: "Pipeline" },
  { key: "export", label: "Export", icon: <ExportIcon size={18} />, stepNum: "06", section: "Pipeline" },
];

interface MenntrAppShellProps {
  currentStep: FactoryStepKey;
  onNavigate: (step: FactoryStepKey) => void;
  batchConfig: AssessmentBatchConfig;
  onUpdateBatchConfig: (config: AssessmentBatchConfig) => void;
  totalDetected: number;
  totalSelected: number;
  validQuestions: number;
  hasSource: boolean;
  hasSchema: boolean;
  hasMapped: boolean;
  children: React.ReactNode;
}

export default function MenntrAppShell({
  currentStep,
  onNavigate,
  batchConfig,
  onUpdateBatchConfig,
  totalDetected,
  totalSelected,
  validQuestions,
  hasSource,
  hasSchema,
  hasMapped,
  children,
}: MenntrAppShellProps) {
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [tempConfig, setTempConfig] = useState<AssessmentBatchConfig>(batchConfig);

  const isGateBlocked = totalSelected > 0 && validQuestions < totalSelected;
  const isGateReady = totalSelected > 0 && validQuestions === totalSelected;

  const sections = Array.from(new Set(NAV_ITEMS.map((item) => item.section)));

  const handleSaveConfig = () => {
    onUpdateBatchConfig(tempConfig);
    setShowConfigModal(false);
  };

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="brand-badge">M</div>
          <div>
            <div className="brand-title">Menntr AI</div>
            <div className="brand-subtitle">Assessment Content Factory</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {sections.map((secName) => (
            <div key={secName} style={{ marginBottom: "8px" }}>
              <div className="nav-section-title">{secName}</div>
              {NAV_ITEMS.filter((item) => item.section === secName).map((item) => {
                const isActive = currentStep === item.key;

                let isCompleted = false;
                if (item.key === "templates" && hasSchema) isCompleted = true;
                if (item.key === "source" && hasSource) isCompleted = true;
                if (item.key === "selection" && totalDetected > 0) isCompleted = true;
                if (item.key === "review" && hasMapped && totalSelected > 0) isCompleted = true;
                if (item.key === "quality" && hasMapped) isCompleted = true;

                return (
                  <div
                    key={item.key}
                    className={`nav-item ${isActive ? "active" : ""} ${isCompleted ? "completed" : ""}`}
                    onClick={() => onNavigate(item.key)}
                  >
                    <span className="nav-item-icon">{item.icon}</span>
                    <span>{item.label}</span>
                    <span className="nav-item-step">{item.stepNum}</span>
                  </div>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="pipeline-status-card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
              <span style={{ color: "var(--text-secondary)", fontWeight: 600, fontSize: "0.75rem" }}>Active Assessment</span>
              <button
                className="secondary"
                onClick={() => {
                  setTempConfig(batchConfig);
                  setShowConfigModal(true);
                }}
                style={{ padding: "2px 6px", fontSize: "0.7rem", gap: "4px" }}
              >
                <EditIcon size={12} /> Edit
              </button>
            </div>
            <div style={{ color: "var(--text-primary)", fontWeight: 600, fontSize: "0.82rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {batchConfig.assessmentName || "Untitled Assessment"}
            </div>
            <div style={{ color: "var(--text-muted)", fontSize: "0.74rem", marginTop: "4px" }}>
              {totalDetected > 0 ? (
                <>
                  <strong style={{ color: "var(--text-primary)" }}>{totalDetected}</strong> extracted • <strong style={{ color: "var(--primary-hover)" }}>{totalSelected}</strong> selected
                </>
              ) : (
                "No source uploaded yet"
              )}
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="app-main">
        {/* Topbar */}
        <header className="topbar">
          <div className="topbar-left">
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <span className="topbar-batch-title">
                {batchConfig.assessmentName || "Assessment Content Factory"}
              </span>

              <span
                className="topbar-meta-chip"
                style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: "6px" }}
                onClick={() => {
                  setTempConfig(batchConfig);
                  setShowConfigModal(true);
                }}
              >
                {batchConfig.subject} • {batchConfig.gradeClass}
                <EditIcon size={12} color="var(--text-muted)" />
              </span>

              {totalDetected > 0 && (
                <span className="topbar-meta-chip" style={{ background: "rgba(59, 130, 246, 0.12)", color: "#93C5FD", border: "1px solid rgba(59, 130, 246, 0.25)" }}>
                  {totalDetected} Extracted • {totalSelected} Selected
                </span>
              )}
            </div>
          </div>

          <div className="topbar-right">
            {totalSelected === 0 ? (
              <span className="quality-gate-pill in-progress">
                Ready to Ingest
              </span>
            ) : isGateReady ? (
              <span className="quality-gate-pill ready" style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                <CheckCircleIcon size={16} /> Ready for Export
              </span>
            ) : (
              <span className="quality-gate-pill blocked" style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                <AlertTriangleIcon size={16} /> Export Blocked ({totalSelected - validQuestions} Issues)
              </span>
            )}
          </div>
        </header>

        {/* Workflow Progress Indicator (8 Steps) */}
        <main className="content-container">
          <div className="workflow-progress-bar">
            {NAV_ITEMS.map((item, idx) => {
              const isActive = currentStep === item.key;
              const stepIndex = NAV_ITEMS.findIndex((n) => n.key === currentStep);
              const isPast = stepIndex > idx;

              return (
                <React.Fragment key={item.key}>
                  <div
                    className={`workflow-node ${isActive ? "active" : ""} ${isPast ? "completed" : ""}`}
                    onClick={() => onNavigate(item.key)}
                  >
                    <div className="workflow-node-bullet">
                      {isPast ? <CheckIcon size={12} color="#FFFFFF" /> : idx + 1}
                    </div>
                    <span>{item.label}</span>
                  </div>
                  {idx < NAV_ITEMS.length - 1 && (
                    <span className="workflow-separator">
                      <ArrowRightIcon size={12} color="var(--border-medium)" />
                    </span>
                  )}
                </React.Fragment>
              );
            })}
          </div>

          {children}
        </main>
      </div>

      {/* Assessment Details Edit Modal */}
      {showConfigModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.75)",
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
              maxWidth: "600px",
              width: "100%",
              boxShadow: "0 20px 40px rgba(0, 0, 0, 0.5)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
              <div style={{ fontWeight: 700, fontSize: "1.15rem", color: "var(--text-primary)" }}>
                Edit Assessment Details
              </div>
              <button
                className="secondary"
                onClick={() => setShowConfigModal(false)}
                style={{ padding: "4px 8px" }}
              >
                <XIcon size={16} />
              </button>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
              <div style={{ gridColumn: "1 / -1" }}>
                <label>Assessment Name *</label>
                <input
                  type="text"
                  value={tempConfig.assessmentName}
                  onChange={(e) => setTempConfig({ ...tempConfig, assessmentName: e.target.value })}
                />
              </div>

              <div>
                <label>Subject</label>
                <select
                  value={tempConfig.subject}
                  onChange={(e) => setTempConfig({ ...tempConfig, subject: e.target.value })}
                >
                  <option value="Mathematics">Mathematics</option>
                  <option value="Physics">Physics</option>
                  <option value="Chemistry">Chemistry</option>
                  <option value="Biology">Biology</option>
                  <option value="Science">Science (General)</option>
                  <option value="English">English</option>
                  <option value="Computer Science">Computer Science</option>
                  <option value="Social Studies">Social Studies</option>
                </select>
              </div>

              <div>
                <label>Grade / Class</label>
                <select
                  value={tempConfig.gradeClass}
                  onChange={(e) => setTempConfig({ ...tempConfig, gradeClass: e.target.value })}
                >
                  <option value="Class 6">Class 6</option>
                  <option value="Class 7">Class 7</option>
                  <option value="Class 8">Class 8</option>
                  <option value="Class 9">Class 9</option>
                  <option value="Class 10">Class 10</option>
                  <option value="Class 11">Class 11</option>
                  <option value="Class 12">Class 12</option>
                  <option value="Higher Ed">Higher Ed / Competitive</option>
                </select>
              </div>

              <div>
                <label>Chapter / Topic</label>
                <input
                  type="text"
                  value={tempConfig.chapterTopic}
                  onChange={(e) => setTempConfig({ ...tempConfig, chapterTopic: e.target.value })}
                />
              </div>

              <div>
                <label>Question Type Focus</label>
                <select
                  value={tempConfig.questionType}
                  onChange={(e) => setTempConfig({ ...tempConfig, questionType: e.target.value })}
                >
                  <option value="Multiple Choice (MCQ)">Multiple Choice (MCQ)</option>
                  <option value="Multiple Response">Multiple Response</option>
                  <option value="Assertion & Reasoning">Assertion & Reasoning</option>
                  <option value="Fill in the Blanks">Fill in the Blanks</option>
                  <option value="Mixed Item Bank">Mixed Item Bank</option>
                </select>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px", marginTop: "24px" }}>
              <button className="secondary" onClick={() => setShowConfigModal(false)}>
                Cancel
              </button>
              <button className="primary" onClick={handleSaveConfig}>
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
