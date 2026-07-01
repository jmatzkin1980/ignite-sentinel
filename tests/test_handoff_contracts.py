from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sentinel.handoff_contracts import load_handoff_contract_registry
from sentinel.validation import cross_artifact_consistency


class HandoffContractTests(unittest.TestCase):
    def test_loads_default_registry_with_existing_check_reference(self) -> None:
        registry = load_handoff_contract_registry()
        contracts = {contract["id"]: contract for contract in registry["contracts"]}

        self.assertIn("discovery_to_brief_minimum", contracts)
        self.assertEqual(contracts["discovery_to_brief_minimum"]["edge"], "discovery->brief")
        self.assertEqual(
            contracts["spec_unit_story_handoff"]["existing_check"],
            "spec_unit_story_handoff",
        )

    def test_discovery_to_brief_missing_declared_field_warns(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sentinel_handoff_contract_") as temp:
            base = Path(temp)
            brief_dir = base / "02_requirements"
            brief_dir.mkdir(parents=True)
            (brief_dir / "project-brief.md").write_text(
                "\n".join(
                    [
                        "# Project Brief",
                        "",
                        "## Objetivo",
                        "Reducir el tiempo de revision operativa.",
                        "",
                        "## Usuarios",
                        "El usuario principal es el supervisor operativo.",
                    ]
                ),
                encoding="utf-8",
            )

            result = cross_artifact_consistency("CONTRACT", base)

        contract_check = next(
            check
            for check in result["checks"]
            if check["id"] == "handoff_contract:discovery_to_brief_minimum"
        )
        referenced = next(
            check
            for check in result["checks"]
            if check["id"] == "handoff_contract:spec_unit_story_handoff"
        )

        self.assertEqual(contract_check["status"], "WARN")
        self.assertEqual(contract_check["missing_fields"], ["acceptance_or_quality"])
        self.assertEqual(referenced["status"], "REFERENCED")
        self.assertTrue(
            any(
                warning["check"] == "handoff_contract"
                and warning["layer"] == "discovery->brief"
                and "acceptance_or_quality" in warning["message"]
                for warning in result["warnings"]
            )
        )


if __name__ == "__main__":
    unittest.main()
