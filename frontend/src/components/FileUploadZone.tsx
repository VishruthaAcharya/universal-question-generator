"use client";

import React, { useRef } from "react";
import { UploadIcon, FileTextIcon, CheckIcon } from "./icons";

interface FileUploadZoneProps {
  file: File | null;
  accept: string;
  onFileChange: (file: File) => void;
  title?: string;
  supportedFormatsText: string;
  successBadgeText?: string;
}

export default function FileUploadZone({
  file,
  accept,
  onFileChange,
  title = "Drag & drop or click to browse",
  supportedFormatsText,
  successBadgeText = "File Uploaded Successfully",
}: FileUploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      onFileChange(selected);
    }
  };

  return (
    <>
      <input
        type="file"
        ref={inputRef}
        accept={accept}
        onChange={handleInputChange}
      />
      <div
        className={`file-upload-zone ${file ? "has-file" : ""}`}
        onClick={() => inputRef.current?.click()}
      >
        {file ? (
          <>
            <div style={{ padding: "12px", borderRadius: "50%", background: "rgba(16, 185, 129, 0.12)", color: "var(--accent)" }}>
              <FileTextIcon size={32} />
            </div>
            <strong style={{ fontSize: "0.95rem", color: "var(--text-primary)" }}>{file.name}</strong>
            <span className="badge success" style={{ gap: "4px" }}>
              <CheckIcon size={12} /> {successBadgeText}
            </span>
          </>
        ) : (
          <>
            <div style={{ padding: "12px", borderRadius: "50%", background: "rgba(59, 130, 246, 0.1)", color: "var(--primary-hover)" }}>
              <UploadIcon size={32} />
            </div>
            <strong style={{ fontSize: "0.95rem", color: "var(--text-primary)" }}>{title}</strong>
            <span style={{ color: "var(--text-secondary)", fontSize: "0.82rem" }}>{supportedFormatsText}</span>
          </>
        )}
      </div>
    </>
  );
}
