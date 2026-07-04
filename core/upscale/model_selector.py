import json
from pathlib import Path

class ModelSelector:
    def __init__(self):
        self.rules = self._load_rules()

    def _load_rules(self):
        rules_path = Path(__file__).parent / "rules.json"
        if rules_path.exists():
            with open(rules_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def select(self, features: dict) -> dict:
        reason_tree = []
        selected_model = "ultrasharp" # default fallback
        confidence = 0.0

        if "error" in features:
            return {
                "selected_model": selected_model,
                "confidence": 0.0,
                "reason_tree": ["Error in features -> Fallback"],
                "strategy": "Fallback"
            }

        # Sort rules by priority
        sorted_rules = sorted(self.rules.items(), key=lambda x: x[1].get("priority", 99))

        for model_name, rule in sorted_rules:
            if rule.get("logic") == "DEFAULT":
                continue

            conditions = rule.get("conditions", [])
            logic = rule.get("logic", "AND")
            
            match_results = []
            for cond in conditions:
                feat = cond["feature"]
                op = cond["operator"]
                val = cond["value"]
                
                if feat not in features:
                    match_results.append((False, f"{feat} missing"))
                    continue
                    
                actual = features[feat]
                matched = False
                
                if op == ">": matched = actual > val
                elif op == "<": matched = actual < val
                elif op == ">=": matched = actual >= val
                elif op == "<=": matched = actual <= val
                elif op == "==": matched = actual == val
                
                reason = f"{feat} ({actual:.3f}) {op} {val} -> {matched}"
                match_results.append((matched, reason))

            if not match_results:
                continue

            bools = [m[0] for m in match_results]
            if logic == "AND":
                is_match = all(bools)
            else:
                is_match = any(bools)

            if is_match:
                selected_model = model_name
                confidence = 100.0 if logic == "AND" else 80.0
                reason_tree.append(f"Evaluated {model_name} ({logic}):")
                for m in match_results:
                    reason_tree.append("  - " + m[1])
                reason_tree.append(f"-> MATCH! Selected {model_name}")
                break
            else:
                reason_tree.append(f"Evaluated {model_name} ({logic}):")
                for m in match_results:
                    reason_tree.append("  - " + m[1])
                reason_tree.append(f"-> FAILED")

        if selected_model == "ultrasharp":
            reason_tree.append("-> Fallback to ultrasharp")
            confidence = 100.0

        return {
            "selected_model": selected_model,
            "confidence": confidence,
            "reason_tree": reason_tree,
            "strategy": "Auto"
        }
