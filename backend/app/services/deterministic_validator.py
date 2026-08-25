import re
import math
import ast
from typing import Any

# Subject keyword heuristics
MATH_KEYWORDS = {"math", "mathematics", "algebra", "geometry", "calculus", "trigonometry", "arithmetic", "quadratic", "fraction", "probability", "percent", "derivative", "integral"}
PHYSICS_KEYWORDS = {"physics", "force", "velocity", "acceleration", "gravity", "energy", "joule", "newton", "watt", "ohm", "current", "voltage", "resistance", "motion", "optics", "kinematics", "momentum"}
CHEMISTRY_KEYWORDS = {"chemistry", "chemical", "reaction", "formula", "element", "atom", "molecule", "acid", "base", "ph", "stoichiometry", "valency", "molar", "compound", "periodic table"}
BIOLOGY_KEYWORDS = {"biology", "cell", "organ", "dna", "rna", "photosynthesis", "mitochondria", "organism", "species", "plant", "animal", "tissue", "enzyme", "respiration", "reproduction"}

# SI Units Knowledge Base
PHYSICS_UNITS = {
    "force": "newton",
    "energy": "joule",
    "work": "joule",
    "power": "watt",
    "electric current": "ampere",
    "current": "ampere",
    "electric resistance": "ohm",
    "resistance": "ohm",
    "voltage": "volt",
    "potential difference": "volt",
    "electric charge": "coulomb",
    "charge": "coulomb",
    "frequency": "hertz",
    "pressure": "pascal",
    "capacitance": "farad",
    "magnetic field": "tesla",
    "inductance": "henry",
    "temperature": "kelvin",
    "mass": "kilogram",
    "length": "meter",
    "time": "second"
}

# Chemistry Common Knowledge Base
CHEMISTRY_NAMES = {
    "h2o": "water",
    "co2": "carbon dioxide",
    "nacl": "sodium chloride",
    "hcl": "hydrochloric acid",
    "h2so4": "sulfuric acid",
    "ch4": "methane",
    "nh3": "ammonia",
    "o2": "oxygen",
    "n2": "nitrogen",
    "c6h12o6": "glucose",
    "caco3": "calcium carbonate",
    "naoh": "sodium hydroxide"
}

# Biology Core Terminology
BIOLOGY_TERMS = {
    "powerhouse of the cell": "mitochondria",
    "site of photosynthesis": "chloroplast",
    "kitchen of the cell": "chloroplast",
    "genetic material": "dna",
    "protein synthesis site": "ribosome",
    "suicide bags of the cell": "lysosome",
    "functional unit of kidney": "nephron",
    "functional unit of nervous system": "neuron",
    "structural and functional unit of life": "cell",
    "carrier of oxygen in blood": "hemoglobin",
    "universal blood donor": "o negative",
    "universal blood recipient": "ab positive"
}

def detect_subject(question_stem: str, topic_hint: str = "", context_subject: str = "") -> str:
    """
    Detects whether the question domain is Mathematics, Physics, Chemistry, Biology, or General.
    """
    combined = f"{context_subject} {topic_hint} {question_stem}".lower()
    
    # Check context/topic first
    if any(k in context_subject.lower() for k in ["math", "algebra", "geometry"]):
        return "Mathematics"
    if any(k in context_subject.lower() for k in ["physic"]):
        return "Physics"
    if any(k in context_subject.lower() for k in ["chem"]):
        return "Chemistry"
    if any(k in context_subject.lower() for k in ["bio"]):
        return "Biology"

    # Score based on keywords
    scores = {
        "Mathematics": sum(1 for kw in MATH_KEYWORDS if re.search(rf"\b{kw}\b", combined)),
        "Physics": sum(1 for kw in PHYSICS_KEYWORDS if re.search(rf"\b{kw}\b", combined)),
        "Chemistry": sum(1 for kw in CHEMISTRY_KEYWORDS if re.search(rf"\b{kw}\b", combined)),
        "Biology": sum(1 for kw in BIOLOGY_KEYWORDS if re.search(rf"\b{kw}\b", combined)),
    }
    
    top_subject, top_score = max(scores.items(), key=lambda x: x[1])
    if top_score > 0:
        return top_subject
    return "General"

def evaluate_math_expression(expr_str: str) -> float | int | None:
    """Safely evaluates basic arithmetic expressions using AST."""
    try:
        # Clean expression
        clean = expr_str.replace("^", "**").replace("×", "*").replace("÷", "/")
        # Allow only safe math operators and numbers
        node = ast.parse(clean, mode='eval')
        
        def _eval(node):
            if isinstance(node, ast.Expression):
                return _eval(node.body)
            elif isinstance(node, ast.Constant):
                return node.value
            elif isinstance(node, ast.BinOp):
                left = _eval(node.left)
                right = _eval(node.right)
                if isinstance(node.op, ast.Add):
                    return left + right
                elif isinstance(node.op, ast.Sub):
                    return left - right
                elif isinstance(node.op, ast.Mult):
                    return left * right
                elif isinstance(node.op, ast.Div):
                    return left / right
                elif isinstance(node.op, ast.Pow):
                    return left ** right
                elif isinstance(node.op, ast.Mod):
                    return left % right
            elif isinstance(node, ast.UnaryOp):
                operand = _eval(node.operand)
                if isinstance(node.op, ast.UAdd):
                    return +operand
                elif isinstance(node.op, ast.USub):
                    return -operand
            raise ValueError("Unsupported AST node")

        return _eval(node)
    except Exception:
        return None

def deterministic_math_solve(question_stem: str, options: list[str]) -> dict[str, Any]:
    """
    Deterministically solves common algebraic, arithmetic, percentage, and quadratic questions.
    """
    stem_lower = question_stem.lower().strip()
    calculated_val = None
    reasoning = None

    # Pattern 1: "What is the value of 2x + 3 when x = 5?" or "If x = 4, find 3x^2 - 2x + 1"
    subst_m = re.search(r"(?:value of|find|evaluate)\s+([0-9x\+\-\*\/\^\s\(\)]+)\s+(?:when|if|for)\s+x\s*=\s*([-+]?\d+(?:\.\d+)?)", question_stem, re.IGNORECASE)
    if subst_m:
        expr_raw, x_val_str = subst_m.group(1), subst_m.group(2)
        try:
            x_val = float(x_val_str)
            # Replace 2x with 2*x, 3x^2 with 3*(x**2)
            expr_prepared = re.sub(r"(\d+)x", r"\1*x", expr_raw)
            expr_prepared = expr_prepared.replace("x", f"({x_val})")
            val = evaluate_math_expression(expr_prepared)
            if val is not None:
                calculated_val = val
                reasoning = f"Substituted x = {x_val_str} into {expr_raw.strip()} = {val}."
        except Exception:
            pass

    # Pattern 2: "What is 15 * 8?" or "Calculate 48 / 6" or "Evaluate (12 + 8) * 3"
    if calculated_val is None:
        calc_m = re.search(r"(?:what is|calculate|evaluate|solve)\s+([0-9\+\-\*\/\^\(\)\.\s]+)\s*\??$", question_stem, re.IGNORECASE)
        if calc_m:
            raw_arith = calc_m.group(1).strip()
            val = evaluate_math_expression(raw_arith)
            if val is not None:
                calculated_val = val
                reasoning = f"Evaluated arithmetic {raw_arith} = {val}."

    # Pattern 3: "What is 20% of 150?"
    if calculated_val is None:
        pct_m = re.search(r"(\d+(?:\.\d+)?)\s*%\s+of\s+(\d+(?:\.\d+)?)", question_stem, re.IGNORECASE)
        if pct_m:
            pct_val = float(pct_m.group(1))
            total_val = float(pct_m.group(2))
            calculated_val = (pct_val / 100.0) * total_val
            reasoning = f"Calculated {pct_val}% of {total_val} = {calculated_val}."

    # Pattern 4: Quadratic roots "roots of x^2 - 5x + 6 = 0"
    if calculated_val is None:
        quad_m = re.search(r"roots of\s+x\^?2\s*([+-]\s*\d+)?x\s*([+-]\s*\d+)?\s*=\s*0", question_stem, re.IGNORECASE)
        if quad_m:
            try:
                b_str = (quad_m.group(1) or "+1").replace(" ", "")
                c_str = (quad_m.group(2) or "+0").replace(" ", "")
                b = float(b_str)
                c = float(c_str)
                a = 1.0
                disc = b**2 - 4*a*c
                if disc >= 0:
                    r1 = (-b + math.sqrt(disc)) / (2*a)
                    r2 = (-b - math.sqrt(disc)) / (2*a)
                    calculated_val = f"{int(r1) if r1.is_integer() else r1}, {int(r2) if r2.is_integer() else r2}"
                    reasoning = f"Roots of quadratic equation: x = {r1}, x = {r2}."
            except Exception:
                pass

    if calculated_val is not None and options:
        # Match calculated value with options
        matched_letter, matched_text = match_value_to_options(calculated_val, options)
        if matched_letter:
            return {
                "verified": True,
                "selected_option_letter": matched_letter,
                "selected_option_text": matched_text,
                "reasoning": reasoning,
                "method": "DETERMINISTIC_MATH"
            }

    return {"verified": False, "selected_option_letter": None, "reasoning": None}

def deterministic_physics_solve(question_stem: str, options: list[str]) -> dict[str, Any]:
    """
    Deterministically validates physics questions (SI units, dimensional checks, basic formulas).
    """
    stem_lower = question_stem.lower()

    # Check SI unit question: "SI unit of force is" or "What is the SI unit of power?"
    for quantity, expected_unit in PHYSICS_UNITS.items():
        if f"si unit of {quantity}" in stem_lower or f"unit of {quantity}" in stem_lower:
            matched_letter, matched_text = match_text_to_options(expected_unit, options)
            if matched_letter:
                return {
                    "verified": True,
                    "selected_option_letter": matched_letter,
                    "selected_option_text": matched_text,
                    "reasoning": f"The SI unit of {quantity} is {expected_unit.capitalize()}.",
                    "method": "DETERMINISTIC_PHYSICS"
                }

    # Numerical formulas: F = m * a
    f_m = re.search(r"mass\s*(?:of|=)\s*(\d+(?:\.\d+)?)\s*kg.*acceleration\s*(?:of|=)\s*(\d+(?:\.\d+)?)\s*m/s\^?2", question_stem, re.IGNORECASE)
    if f_m:
        m_val = float(f_m.group(1))
        a_val = float(f_m.group(2))
        force = m_val * a_val
        matched_letter, matched_text = match_value_to_options(force, options)
        if matched_letter:
            return {
                "verified": True,
                "selected_option_letter": matched_letter,
                "selected_option_text": matched_text,
                "reasoning": f"Calculated Force F = m * a = {m_val} kg * {a_val} m/s^2 = {force} N.",
                "method": "DETERMINISTIC_PHYSICS"
            }

    return {"verified": False, "selected_option_letter": None, "reasoning": None}

def deterministic_chemistry_solve(question_stem: str, options: list[str]) -> dict[str, Any]:
    """
    Deterministically validates chemical names and formulas.
    """
    stem_lower = question_stem.lower()

    # Chemical formula lookup: "What is the chemical formula of water?" or "Formula of Carbon Dioxide"
    for formula, name in CHEMISTRY_NAMES.items():
        if f"formula of {name}" in stem_lower or f"chemical formula for {name}" in stem_lower:
            matched_letter, matched_text = match_text_to_options(formula, options)
            if matched_letter:
                return {
                    "verified": True,
                    "selected_option_letter": matched_letter,
                    "selected_option_text": matched_text,
                    "reasoning": f"The chemical formula for {name.title()} is {formula.upper()}.",
                    "method": "DETERMINISTIC_CHEMISTRY"
                }
        elif f"what is {formula}" in stem_lower or f"name of {formula}" in stem_lower:
            matched_letter, matched_text = match_text_to_options(name, options)
            if matched_letter:
                return {
                    "verified": True,
                    "selected_option_letter": matched_letter,
                    "selected_option_text": matched_text,
                    "reasoning": f"{formula.upper()} is the chemical formula for {name.title()}.",
                    "method": "DETERMINISTIC_CHEMISTRY"
                }

    return {"verified": False, "selected_option_letter": None, "reasoning": None}

def deterministic_biology_solve(question_stem: str, options: list[str]) -> dict[str, Any]:
    """
    Deterministically validates standard biological terms and organelle functions.
    """
    stem_lower = question_stem.lower()

    for query, expected_answer in BIOLOGY_TERMS.items():
        if query in stem_lower:
            matched_letter, matched_text = match_text_to_options(expected_answer, options)
            if matched_letter:
                return {
                    "verified": True,
                    "selected_option_letter": matched_letter,
                    "selected_option_text": matched_text,
                    "reasoning": f"{expected_answer.title()} is known as the {query}.",
                    "method": "DETERMINISTIC_BIOLOGY"
                }

    return {"verified": False, "selected_option_letter": None, "reasoning": None}

def match_value_to_options(val: Any, options: list[str]) -> tuple[str | None, str | None]:
    """
    Matches a calculated number or string against the options list.
    """
    if not options:
        return None, None

    val_str = str(val).strip()
    val_num = None
    try:
        val_num = float(val_str)
    except Exception:
        pass

    for i, opt in enumerate(options):
        letter = chr(65 + i)
        opt_clean = opt.strip()
        
        # Direct string equality or substring
        if val_str.lower() == opt_clean.lower() or val_str.lower() in opt_clean.lower().split():
            return letter, opt_clean
            
        # Numerical equality
        if val_num is not None:
            # Extract numbers from option text (e.g. "13", "13 N", "13.0")
            num_matches = re.findall(r"[-+]?\d+(?:\.\d+)?", opt_clean)
            for nm in num_matches:
                try:
                    if math.isclose(float(nm), val_num, rel_tol=1e-3, abs_tol=1e-3):
                        return letter, opt_clean
                except Exception:
                    pass

    return None, None

def match_text_to_options(target_text: str, options: list[str]) -> tuple[str | None, str | None]:
    """
    Matches a target keyword or phrase against option texts.
    """
    if not options or not target_text:
        return None, None

    target_clean = "".join(target_text.lower().split())
    for i, opt in enumerate(options):
        letter = chr(65 + i)
        opt_clean = "".join(opt.lower().split())
        if target_clean in opt_clean or opt_clean in target_clean:
            return letter, opt.strip()

    return None, None

def run_deterministic_validator(
    question_stem: str,
    options: list[str],
    subject: str = "General",
    topic_hint: str = ""
) -> dict[str, Any]:
    """
    Entry point for running domain-specific deterministic validators.
    """
    detected_sub = detect_subject(question_stem, topic_hint, subject)

    if detected_sub == "Mathematics":
        res = deterministic_math_solve(question_stem, options)
        if res.get("verified"):
            res["subject"] = "Mathematics"
            return res

    elif detected_sub == "Physics":
        res = deterministic_physics_solve(question_stem, options)
        if res.get("verified"):
            res["subject"] = "Physics"
            return res

    elif detected_sub == "Chemistry":
        res = deterministic_chemistry_solve(question_stem, options)
        if res.get("verified"):
            res["subject"] = "Chemistry"
            return res

    elif detected_sub == "Biology":
        res = deterministic_biology_solve(question_stem, options)
        if res.get("verified"):
            res["subject"] = "Biology"
            return res

    # If domain-specific didn't trigger, attempt general math/physics in case of misclassification
    math_res = deterministic_math_solve(question_stem, options)
    if math_res.get("verified"):
        math_res["subject"] = "Mathematics"
        return math_res

    phys_res = deterministic_physics_solve(question_stem, options)
    if phys_res.get("verified"):
        phys_res["subject"] = "Physics"
        return phys_res

    chem_res = deterministic_chemistry_solve(question_stem, options)
    if chem_res.get("verified"):
        chem_res["subject"] = "Chemistry"
        return chem_res

    bio_res = deterministic_biology_solve(question_stem, options)
    if bio_res.get("verified"):
        bio_res["subject"] = "Biology"
        return bio_res

    return {
        "verified": False,
        "selected_option_letter": None,
        "selected_option_text": None,
        "reasoning": None,
        "subject": detected_sub,
        "method": "NONE"
    }
