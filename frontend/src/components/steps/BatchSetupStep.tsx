"use client";

import React from "react";
import { AssessmentBatchConfig } from "../../types";

interface BatchSetupStepProps {
  config: AssessmentBatchConfig;
  onChange: (config: AssessmentBatchConfig) => void;
  onNext: () => void;
}

export default function BatchSetupStep({ config, onChange, onNext }: BatchSetupStepProps) {
  const updateField = (field: keyof AssessmentBatchConfig, value: any) => {
    onChange({
      ...config,
      [field]: value,
    });
  };

  const isFormValid = Boolean(config.assessmentName.trim());

  return (
    <section className="card">
      <div className="card-header-flex">
        <div>
          <div className="card-title">
            <span>⚙️</span> Assessment Batch Configuration
          </div>
          <div className="card-subtitle">
            Configure metadata, curriculum tagging, and target standards for this assessment ingestion batch.
          </div>
        </div>
        <span className="badge info">Step 01 / 09</span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "20px", marginTop: "16px" }}>
        <div>
          <label>Assessment Batch Title *</label>
          <input
            type="text"
            placeholder="e.g. Grade 10 CBSE Mathematics Periodic Test 1"
            value={config.assessmentName}
            onChange={(e) => updateField("assessmentName", e.target.value)}
          />
          <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "4px", display: "block" }}>
            Used across reports, quality certificates, and target exports.
          </span>
        </div>

        <div>
          <label>Subject / Domain</label>
          <select
            value={config.subject}
            onChange={(e) => updateField("subject", e.target.value)}
          >
            <option value="Mathematics">Mathematics</option>
            <option value="Physics">Physics</option>
            <option value="Chemistry">Chemistry</option>
            <option value="Biology">Biology</option>
            <option value="Science (General)">Science (General)</option>
            <option value="English Language & Literature">English Language & Literature</option>
            <option value="Social Studies">Social Studies</option>
            <option value="Computer Science">Computer Science</option>
            <option value="Other">Other / Custom</option>
          </select>
        </div>

        <div>
          <label>Grade / Target Class</label>
          <select
            value={config.gradeClass}
            onChange={(e) => updateField("gradeClass", e.target.value)}
          >
            <option value="Class 6">Class 6 (Middle School)</option>
            <option value="Class 7">Class 7 (Middle School)</option>
            <option value="Class 8">Class 8 (Middle School)</option>
            <option value="Class 9">Class 9 (Secondary)</option>
            <option value="Class 10">Class 10 (Secondary)</option>
            <option value="Class 11">Class 11 (Senior Secondary)</option>
            <option value="Class 12">Class 12 (Senior Secondary)</option>
            <option value="Higher Ed / Competitive">Higher Ed / Competitive</option>
          </select>
        </div>

        <div>
          <label>Chapter / Curriculum Unit</label>
          <input
            type="text"
            placeholder="e.g. Unit 4: Quadratic Equations & Polynomials"
            value={config.chapterTopic}
            onChange={(e) => updateField("chapterTopic", e.target.value)}
          />
        </div>

        <div>
          <label>Primary Question Format</label>
          <select
            value={config.questionType}
            onChange={(e) => updateField("questionType", e.target.value)}
          >
            <option value="Multiple Choice (MCQ Single Correct)">Multiple Choice (MCQ Single Correct)</option>
            <option value="Multiple Response (Multi-Correct)">Multiple Response (Multi-Correct)</option>
            <option value="Assertion & Reasoning">Assertion & Reasoning</option>
            <option value="Fill in the Blanks">Fill in the Blanks</option>
            <option value="Numerical Value Type">Numerical Value Type</option>
            <option value="Mixed Item Bank">Mixed Item Bank</option>
          </select>
        </div>

        <div>
          <label>Assessment Language</label>
          <select
            value={config.language}
            onChange={(e) => updateField("language", e.target.value)}
          >
            <option value="English">English</option>
            <option value="Hindi">Hindi</option>
            <option value="Bilingual (English + Regional)">Bilingual (English + Regional)</option>
            <option value="Spanish">Spanish</option>
            <option value="French">French</option>
          </select>
        </div>
      </div>

      {/* Batch Overview Card */}
      <div
        style={{
          marginTop: "28px",
          padding: "20px",
          background: "var(--bg-surface)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "12px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div>
          <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-primary)" }}>
            Ingestion Pipeline Specifications
          </div>
          <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginTop: "4px" }}>
            Target: Menntr AI Assessment Certification standard • Quality Gate: Zero-Defect Blockers
          </div>
        </div>

        <button
          className="primary"
          onClick={onNext}
          disabled={!isFormValid}
          style={{ minWidth: "180px" }}
        >
          Initialize Batch & Upload Source →
        </button>
      </div>
    </section>
  );
}
