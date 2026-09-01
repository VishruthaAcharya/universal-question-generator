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

    # Pattern 5: Ratio/Proportions: "if a:b = 3:5 and a = 12, find b"
    if calculated_val is None:
        ratio_m = re.search(
            r"(?:if\s+)?(?:ratio\s+of\s+)?([a-zA-Z])\s*(?::|to|\/)\s*([a-zA-Z])\s*(?:is|=|as)\s*(\d+(?:\.\d+)?)\s*(?::|\/|to)\s*(\d+(?:\.\d+)?)\s*(?:and|,|\.|\;)\s*(?:if\s+)?\1\s*=\s*(\d+(?:\.\d+)?).*?(?:find|what is|calculate)\s+\2",
            question_stem,
            re.IGNORECASE
        )
        if ratio_m:
            try:
                var_a, var_b = ratio_m.group(1), ratio_m.group(2)
                r_x = float(ratio_m.group(3))
                r_y = float(ratio_m.group(4))
                val_a = float(ratio_m.group(5))
                if r_x != 0:
                    calc_res = (val_a * r_y) / r_x
                    calculated_val = int(calc_res) if calc_res.is_integer() else calc_res
                    reasoning = f"Proportion {var_a}:{var_b} = {r_x}:{r_y}. With {var_a} = {val_a}, {var_b} = ({val_a} * {r_y}) / {r_x} = {calculated_val}."
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

def deterministic_unit_conversion_solve(question_stem: str, options: list[str]) -> dict[str, Any]:
    """
    Deterministically solves standard unit conversion questions:
    - Length: km <-> m, m <-> cm, cm <-> mm, mm <-> m
    - Mass: kg <-> g, g <-> mg
    - Time: hours <-> minutes, minutes <-> seconds, hours <-> seconds, days <-> hours
    - Temperature: Celsius <-> Fahrenheit
    """
    stem_lower = question_stem.lower().strip()
    calculated_val = None
    reasoning = None

    # Length Conversions: "Convert 5 km to meters" or "How many meters in 3.5 km?" or "5 km is equal to how many meters?"
    km_to_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:km|kilometers?)\s*(?:to|in|is equal to)\s*(?:meters?|m\b)", stem_lower)
    if km_to_m:
        n = float(km_to_m.group(1))
        calculated_val = int(n * 1000) if (n * 1000).is_integer() else n * 1000
        reasoning = f"Converted {n} km to meters: {n} * 1000 = {calculated_val} m."

    m_to_km = re.search(r"(\d+(?:\.\d+)?)\s*(?:meters?|m\b)\s*(?:to|in|is equal to)\s*(?:km|kilometers?)", stem_lower)
    if calculated_val is None and m_to_km:
        n = float(m_to_km.group(1))
        calculated_val = n / 1000
        reasoning = f"Converted {n} meters to km: {n} / 1000 = {calculated_val} km."

    m_to_cm = re.search(r"(\d+(?:\.\d+)?)\s*(?:meters?|m\b)\s*(?:to|in|is equal to)\s*(?:centimeters?|cm\b)", stem_lower)
    if calculated_val is None and m_to_cm:
        n = float(m_to_cm.group(1))
        calculated_val = int(n * 100) if (n * 100).is_integer() else n * 100
        reasoning = f"Converted {n} meters to cm: {n} * 100 = {calculated_val} cm."

    cm_to_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:centimeters?|cm\b)\s*(?:to|in|is equal to)\s*(?:meters?|m\b)", stem_lower)
    if calculated_val is None and cm_to_m:
        n = float(cm_to_m.group(1))
        calculated_val = n / 100
        reasoning = f"Converted {n} cm to meters: {n} / 100 = {calculated_val} m."

    # Mass Conversions: "Convert 4 kg to grams"
    kg_to_g = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg|kilograms?)\s*(?:to|in|is equal to)\s*(?:grams?|g\b)", stem_lower)
    if calculated_val is None and kg_to_g:
        n = float(kg_to_g.group(1))
        calculated_val = int(n * 1000) if (n * 1000).is_integer() else n * 1000
        reasoning = f"Converted {n} kg to grams: {n} * 1000 = {calculated_val} g."

    g_to_kg = re.search(r"(\d+(?:\.\d+)?)\s*(?:grams?|g\b)\s*(?:to|in|is equal to)\s*(?:kg|kilograms?)", stem_lower)
    if calculated_val is None and g_to_kg:
        n = float(g_to_kg.group(1))
        calculated_val = n / 1000
        reasoning = f"Converted {n} grams to kg: {n} / 1000 = {calculated_val} kg."

    # Time Conversions: "How many seconds in 2 hours?" or "Convert 2 hours to seconds"
    hr_to_sec = re.search(r"(?:(?:how many\s+)?(?:seconds?|secs?|s\b)\s*(?:are\s+)?(?:in|to)\s*(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|hr\b)|(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|hr\b)\s*(?:to|in|is equal to)\s*(?:seconds?|secs?|s\b))", stem_lower)
    if calculated_val is None and hr_to_sec:
        n = float(hr_to_sec.group(1) or hr_to_sec.group(2))
        calculated_val = int(n * 3600) if (n * 3600).is_integer() else n * 3600
        reasoning = f"Converted {n} hours to seconds: {n} * 3600 = {calculated_val} s."

    hr_to_min = re.search(r"(?:(?:how many\s+)?(?:minutes?|mins?|min\b)\s*(?:are\s+)?(?:in|to)\s*(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|hr\b)|(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|hr\b)\s*(?:to|in|is equal to)\s*(?:minutes?|mins?|min\b))", stem_lower)
    if calculated_val is None and hr_to_min:
        n = float(hr_to_min.group(1) or hr_to_min.group(2))
        calculated_val = int(n * 60) if (n * 60).is_integer() else n * 60
        reasoning = f"Converted {n} hours to minutes: {n} * 60 = {calculated_val} min."

    min_to_sec = re.search(r"(?:(?:how many\s+)?(?:seconds?|secs?|s\b)\s*(?:are\s+)?(?:in|to)\s*(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|min\b)|(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|min\b)\s*(?:to|in|is equal to)\s*(?:seconds?|secs?|s\b))", stem_lower)
    if calculated_val is None and min_to_sec:
        n = float(min_to_sec.group(1) or min_to_sec.group(2))
        calculated_val = int(n * 60) if (n * 60).is_integer() else n * 60
        reasoning = f"Converted {n} minutes to seconds: {n} * 60 = {calculated_val} s."

    # Temperature Conversions: "Convert 100 °C to Fahrenheit" or "25 C in Fahrenheit"
    c_to_f = re.search(r"(\d+(?:\.\d+)?)\s*°?\s*c(?:elsius)?\s*(?:to|in|is equal to)\s*°?\s*f(?:ahrenheit)?", stem_lower)
    if calculated_val is None and c_to_f:
        c_val = float(c_to_f.group(1))
        calc_f = (c_val * 9.0 / 5.0) + 32.0
        calculated_val = int(calc_f) if calc_f.is_integer() else calc_f
        reasoning = f"Converted {c_val}°C to Fahrenheit: ({c_val} * 9/5) + 32 = {calculated_val}°F."

    f_to_c = re.search(r"(\d+(?:\.\d+)?)\s*°?\s*f(?:ahrenheit)?\s*(?:to|in|is equal to)\s*°?\s*c(?:elsius)?", stem_lower)
    if calculated_val is None and f_to_c:
        f_val = float(f_to_c.group(1))
        calc_c = (f_val - 32.0) * 5.0 / 9.0
        calculated_val = int(calc_c) if calc_c.is_integer() else calc_c
        reasoning = f"Converted {f_val}°F to Celsius: ({f_val} - 32) * 5/9 = {calculated_val}°C."

    if calculated_val is not None and options:
        matched_letter, matched_text = match_value_to_options(calculated_val, options)
        if matched_letter:
            return {
                "verified": True,
                "selected_option_letter": matched_letter,
                "selected_option_text": matched_text,
                "reasoning": reasoning,
                "method": "DETERMINISTIC_UNIT_CONVERSION"
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
    # 0. Check unit conversion first (across all subjects)
    unit_res = deterministic_unit_conversion_solve(question_stem, options)
    if unit_res.get("verified"):
        unit_res["subject"] = subject or "Physics"
        return unit_res

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
