import re
from typing import Any

# Common OCR / legacy font mojibake mappings for math & physics symbols in educational PDFs
MOJIBAKE_MAP = {
    # Degrees and angles
    re.compile(r"(\d+)\s*(?:b0|\s*b0|\ufffdb0|\ufffd\s*b0|Â°|Â\s*°|\bdegrees?\b)", re.IGNORECASE): r"\1°",
    re.compile(r"(\d+)°\s*C", re.IGNORECASE): r"\1°C",
    
    # Microfarad / Units
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:bcF|bc\s*F|\u00b5F|uF|u\s*F)", re.IGNORECASE): r"\1 μF",
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:bcH|bc\s*H|uH)", re.IGNORECASE): r"\1 μH",
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:bcm|bc\s*m|um)", re.IGNORECASE): r"\1 μm",
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:bcC|bc\s*C|uC)", re.IGNORECASE): r"\1 μC",
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:bcA|bc\s*A|uA)", re.IGNORECASE): r"\1 μA",
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:bcV|bc\s*V|uV)", re.IGNORECASE): r"\1 μV",
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:bcW|bc\s*W|uW)", re.IGNORECASE): r"\1 μW",
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:bcg|bc\s*g|ug)", re.IGNORECASE): r"\1 μg",
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:bcL|bc\s*L|uL)", re.IGNORECASE): r"\1 μL",
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:bc\b)", re.IGNORECASE): r"\1 μ",
    
    # Angular frequency / Ohm / Greek symbols
    re.compile(r"\bac9\b"): "ω",
    re.compile(r"\bac9t\b"): "ωt",
    re.compile(r"\b(\d+)\s*(?:Ohm|Ohms|ohms|ohm)\b"): r"\1 Ω",
    re.compile(r"\b(\d+)\s*k\s*(?:Ohm|Ohms|ohms|ohm|Ω)\b"): r"\1 kΩ",
    re.compile(r"\b(\d+)\s*M\s*(?:Ohm|Ohms|ohms|ohm|Ω)\b"): r"\1 MΩ",
    
    # Specific heats ratio / Gamma
    re.compile(r"\b(Cp/Cv\s*=\s*)b3\b", re.IGNORECASE): r"\1γ",
    re.compile(r"\b([A-Za-z0-9\(\)\s]+=\s*)b3\b"): r"\1γ",
    re.compile(r"\b(gamma|Gamma)\b"): "γ",
    re.compile(r"\b(lambda|Lambda)\b"): "λ",
    re.compile(r"\b(theta|Theta)\b"): "θ",
    re.compile(r"\b(omega|Omega)\b"): "ω",
    
    # Subscript & Superscript numbers / operators
    re.compile(r"10\^(\d+)"): lambda m: "10" + "".join("⁰¹²³⁴⁵⁶⁷⁸⁹"[int(d)] for d in m.group(1)),
    re.compile(r"10\^-(\d+)"): lambda m: "10⁻" + "".join("⁰¹²³⁴⁵⁶⁷⁸⁹"[int(d)] for d in m.group(1)),
    re.compile(r"(\b[A-Za-z]+)\^2\b"): r"\1²",
    re.compile(r"(\b[A-Za-z]+)\^3\b"): r"\1³",
    re.compile(r"(\b[A-Za-z]+)\_(\d+)\b"): lambda m: m.group(1) + "".join("₀₁₂₃₄₅₆₇₈₉"[int(d)] for d in m.group(2)),
    
    # Math operators
    re.compile(r"\s*<=\s*"): " ≤ ",
    re.compile(r"\s*>=\s*"): " ≥ ",
    re.compile(r"\s*\+/\-\s*|\s*\+\-\s*"): " ± ",
    re.compile(r"\s*->\s*|\s*-->\s*"): " → ",
    re.compile(r"\s*<->\s*|\s*<==>\s*"): " ⇌ ",
    re.compile(r"\s*\*\s*(?=10[⁰¹²³⁴⁵⁶⁷⁸⁹⁻])"): " × ",
}

def normalize_math_and_greek_symbols(text: str) -> str:
    """
    Normalizes known font artifacts, mojibake, and legacy encodings
    into clean, standardized UTF-8 mathematical and scientific symbols.
    """
    if not text or not isinstance(text, str):
        return text or ""

    normalized = text
    for pattern, replacement in MOJIBAKE_MAP.items():
        if callable(replacement):
            normalized = pattern.sub(replacement, normalized)
        else:
            normalized = pattern.sub(replacement, normalized)

    # Clean double spaces
    normalized = re.sub(r"[ \t]{2,}", " ", normalized)
    return normalized.strip()

def detect_unresolved_corruption(text: str) -> list[str]:
    """
    Detects unresolvable corrupted characters or abnormal glyph artifacts.
    Returns a list of defect descriptions.
    """
    if not text or not isinstance(text, str):
        return []

    defects = []
    
    # 1. Unicode replacement character  (\ufffd)
    if "\ufffd" in text or "" in text:
        defects.append("Unresolvable replacement character () detected in text.")

    # 2. Control characters (except tab/newline)
    control_chars = re.findall(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", text)
    if control_chars:
        defects.append(f"Non-printable control characters ({len(control_chars)}) detected.")

    # 3. Mojibake fragments like "b0", "bcF", "ac9" unmapped
    suspicious = re.findall(r"(?:[A-Za-z0-9][A-Za-z0-9]|b0|\bbc[A-Z]\b|\bac9\b)", text)
    if suspicious:
        defects.append(f"Suspicious encoding fragment(s) {suspicious} detected.")

    # 4. Truncated single-token garbage options e.g. "3BC", "B1", "R1", "R2"
    if re.match(r"^[A-Z]\d+$|^3BC$", text.strip()):
        defects.append(f"Malformed option token '{text.strip()}' detected.")

    return defects
