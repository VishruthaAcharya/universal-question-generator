import os
import zipfile
from pathlib import Path
from typing import Any
from app.config import settings

class ZipValidationError(Exception):
    pass

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".xls", ".csv", ".txt",
    ".png", ".jpg", ".jpeg", ".webp", ".zip"
}

def is_safe_path(base_dir: Path, target_path: Path) -> bool:
    """Checks if a target path is safe and does not traverse outside the base directory."""
    try:
        resolved_base = base_dir.resolve()
        resolved_target = target_path.resolve()
        return resolved_base in resolved_target.parents or resolved_base == resolved_target
    except Exception:
        return False

def process_and_extract_zip(
    zip_path: str,
    extract_dir: str,
    parent_zip_name: str | None = None,
    depth: int = 1,
    current_file_count: int = 0,
    current_extracted_size: int = 0
) -> dict[str, Any]:
    """
    Safely validates and extracts a ZIP archive, recursively extracting nested ZIPs up to depth 2.
    Enforces size and file limits to prevent decompression bomb attacks.
    """
    if depth > 2:
        raise ZipValidationError("Excessive nested archives detected. Maximum zip depth is 2.")

    zip_path_obj = Path(zip_path)
    extract_dir_obj = Path(extract_dir)
    extract_dir_obj.mkdir(parents=True, exist_ok=True)

    # 1. Validate compressed ZIP file size
    compressed_size = zip_path_obj.stat().st_size
    # Only enforce ZIP file limit on the top-level ZIP
    if depth == 1 and compressed_size > settings.max_zip_size_mb * 1024 * 1024:
        raise ZipValidationError(f"ZIP archive size ({compressed_size / 1024 / 1024:.1f} MB) exceeds maximum limit of {settings.max_zip_size_mb} MB.")

    extracted_files = []
    unsupported_files = []

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            infolist = zf.infolist()
            
            # Check files count limit
            total_zip_files = len([info for info in infolist if not info.is_dir()])
            if current_file_count + total_zip_files > settings.max_files_per_batch:
                raise ZipValidationError(
                    f"Number of files in batch exceeds limit of {settings.max_files_per_batch} files."
                )

            # Check uncompressed sizes and path traversals before extracting anything
            for zinfo in infolist:
                if zinfo.is_dir():
                    continue

                # Check path traversal attempts (absolute path or containing '..')
                filename = zinfo.filename
                if filename.startswith("/") or filename.startswith("\\") or ".." in filename or ":" in filename:
                    raise ZipValidationError(f"Security Warning: Unsafe file path '{filename}' detected inside ZIP.")

                # Calculate total uncompressed size limit
                current_extracted_size += zinfo.file_size
                if current_extracted_size > settings.max_zip_extracted_size_mb * 1024 * 1024:
                    raise ZipValidationError(
                        f"Uncompressed size exceeds limit of {settings.max_zip_extracted_size_mb} MB."
                    )

            # Extract files
            for zinfo in infolist:
                if zinfo.is_dir():
                    continue

                filename = zinfo.filename
                target_file_path = extract_dir_obj / filename

                # Ensure path safety before extraction
                if not is_safe_path(extract_dir_obj, target_file_path):
                    raise ZipValidationError(f"Security Warning: Unsafe path resolution for file '{filename}'.")

                # Extract file
                target_file_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(zinfo) as source, open(target_file_path, "wb") as target:
                    target.write(source.read())

                suffix = target_file_path.suffix.lower()
                
                # Check if it is a nested ZIP
                if suffix == ".zip":
                    nested_extract_dir = extract_dir_obj / f"_nested_{target_file_path.stem}"
                    try:
                        # Recursively process the nested zip
                        nested_res = process_and_extract_zip(
                            zip_path=str(target_file_path),
                            extract_dir=str(nested_extract_dir),
                            parent_zip_name=parent_zip_name or zip_path_obj.name,
                            depth=depth + 1,
                            current_file_count=current_file_count + len(extracted_files),
                            current_extracted_size=current_extracted_size
                        )
                        extracted_files.extend(nested_res["extracted_files"])
                        unsupported_files.extend(nested_res["unsupported_files"])
                    except ZipValidationError as ve:
                        # Propagate validation errors
                        raise ve
                    except Exception as ne:
                        unsupported_files.append({
                            "filename": filename,
                            "parent_source": parent_zip_name or zip_path_obj.name,
                            "reason": f"Failed to parse nested ZIP: {ne}"
                        })
                    finally:
                        # Remove temporary nested zip file
                        try:
                            target_file_path.unlink(missing_ok=True)
                        except Exception:
                            pass
                elif suffix in SUPPORTED_EXTENSIONS:
                    extracted_files.append({
                        "absolute_path": str(target_file_path),
                        "parent_source": parent_zip_name or zip_path_obj.name,
                        "source_file": filename,
                        "size_bytes": zinfo.file_size
                    })
                else:
                    unsupported_files.append({
                        "filename": filename,
                        "parent_source": parent_zip_name or zip_path_obj.name,
                        "reason": f"Unsupported format '{suffix}'"
                    })

    except zipfile.BadZipFile:
        raise ZipValidationError("Invalid or corrupted ZIP archive.")

    return {
        "extracted_files": extracted_files,
        "unsupported_files": unsupported_files
    }
