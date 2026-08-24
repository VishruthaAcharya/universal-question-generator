"use client";

import React from "react";
import type { QuestionRow } from "../types";
import {
  CheckCircleIcon,
  AlertTriangleIcon,
  SparklesIcon,
  EditIcon,
} from "./icons";

interface ReviewTableProps {
  columns: string[];
  questions: QuestionRow[];
  onCellChange: (questionId: string, columnName: string, newValue: string) => void;
}

export default function ReviewTable({
  columns,
  questions,
  onCellChange,
}: ReviewTableProps) {
  return (
    <div className="table-wrapper">
      <table>
        <thead>
          <tr>
            <th style={{ width: "60px", textAlign: "center" }}>Row</th>
            <th style={{ width: "90px", textAlign: "center" }}>Source</th>
            <th style={{ width: "130px" }}>Integrity Status</th>
            {columns.map((col, idx) => (
              <th key={idx} style={{ minWidth: "200px" }}>
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {questions.length === 0 ? (
            <tr>
              <td colSpan={columns.length + 3} style={{ textAlign: "center", padding: "32px", color: "var(--text-muted)" }}>
                No questions match the current filter or search criteria.
              </td>
            </tr>
          ) : (
            questions.map((q) => {
              const isValid = q.validation.valid;
              const sourcePage = q.source_metadata?.source_page;
              return (
                <tr key={q.id}>
                  <td style={{ textAlign: "center", fontWeight: 700, color: "var(--text-secondary)" }}>
                    #{q.row_number}
                  </td>
                  <td style={{ textAlign: "center", color: "var(--text-muted)", fontSize: "0.78rem" }}>
                    {sourcePage ? `p. ${sourcePage}` : "—"}
                  </td>
                  <td>
                    <span
                      className={`badge ${isValid ? "success" : "danger"}`}
                      title={q.validation.errors.join("\n")}
                      style={{ cursor: "default", display: "inline-flex", alignItems: "center", gap: "4px" }}
                    >
                      {isValid ? (
                        <>
                          <CheckCircleIcon size={12} /> Valid
                        </>
                      ) : (
                        <>
                          <AlertTriangleIcon size={12} /> Conflict
                        </>
                      )}
                    </span>
                    {!isValid && (
                      <div
                        style={{
                          fontSize: "0.72rem",
                          color: "var(--danger)",
                          marginTop: "4px",
                          maxWidth: "180px",
                        }}
                      >
                        {q.validation.errors.map((e, idx) => (
                          <div key={idx}>• {e}</div>
                        ))}
                      </div>
                    )}
                  </td>
                  {columns.map((col) => {
                    const cellVal = q.data_json[col] || "";
                    const meta = q.source_metadata?.fields?.[col];
                    const origin = meta?.origin || "missing";
                    const confidence = meta?.confidence;
                    const isDiff = col.toLowerCase().includes("difficulty");

                    return (
                      <td key={col} style={{ position: "relative" }}>
                        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                          {isDiff ? (
                            <select
                              value={cellVal}
                              onChange={(e) => onCellChange(q.id, col, e.target.value)}
                              style={{ padding: "8px 10px", fontSize: "0.82rem" }}
                            >
                              <option value="">— Select Difficulty —</option>
                              <option value="Easy">Easy</option>
                              <option value="Medium">Medium</option>
                              <option value="Hard">Hard</option>
                              <option value="Auto">Auto</option>
                            </select>
                          ) : (
                            <textarea
                              rows={2}
                              value={cellVal}
                              onChange={(e) => onCellChange(q.id, col, e.target.value)}
                              style={{ padding: "8px 10px", fontSize: "0.82rem", lineHeight: "1.4" }}
                            />
                          )}

                          {/* Field metadata origin pill */}
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              fontSize: "0.7rem",
                              marginTop: "2px",
                            }}
                          >
                            {origin === "inferred" && (
                              <span
                                style={{ color: "var(--warning)", display: "inline-flex", alignItems: "center", gap: "3px" }}
                                title={`AI Confidence: ${((confidence ?? 0) * 100).toFixed(0)}%`}
                              >
                                <SparklesIcon size={10} /> AI Inferred ({((confidence ?? 0) * 100).toFixed(0)}%)
                              </span>
                            )}
                            {origin === "user_edited" && (
                              <span style={{ color: "var(--primary-hover)", display: "inline-flex", alignItems: "center", gap: "3px" }}>
                                <EditIcon size={10} /> Edited
                              </span>
                            )}
                            {origin === "missing" && cellVal === "" && (
                              <span style={{ color: "var(--danger)", opacity: 0.8 }}>
                                Empty Field
                              </span>
                            )}
                          </div>
                        </div>
                      </td>
                    );
                  })}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
