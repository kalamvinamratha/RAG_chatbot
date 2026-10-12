import re
from decimal import Decimal
from typing import Any


class MultiDocumentSynthesizer:
    def analyze_cross_document_context(self, chunks: list[dict[str, Any]]) -> dict[str, Any]:
        documents = {}
        findings = {}
        for chunk in chunks:
            doc_id = chunk.get("document_id") or chunk.get("filename", "Unknown")
            documents[doc_id] = chunk.get("filename", "Unknown")
            matches = re.findall(
                r"\b([a-zA-Z]{4,30})\s+(\d+(?:\.\d+)?)\s*(mg|mcg|ml)\b"
                r"(?:\s+(once daily|twice daily|three times daily|daily|bid|tid))?",
                chunk.get("content", ""),
                re.IGNORECASE,
            )
            for drug, amount, unit, frequency in matches:
                regimen = f"{Decimal(amount).normalize()} {unit.lower()}"
                frequency = {
                    "bid": "twice daily",
                    "tid": "three times daily",
                    "once daily": "daily",
                }.get(frequency.lower(), frequency.lower())
                # Unknown frequency is not a disagreement with an explicit frequency.
                findings.setdefault(drug.lower(), []).append((doc_id, regimen, frequency))
        variations = []
        for drug, entries in findings.items():
            if len({entry[0] for entry in entries}) < 2:
                continue
            doses = {entry[1] for entry in entries}
            frequencies = {entry[2] for entry in entries if entry[2]}
            if len(doses) > 1 or len(frequencies) > 1:
                variations.append(
                    {
                        "subject": drug.capitalize(),
                        "type": "Dosage / Regimen Variation",
                        "details": "; ".join(
                            sorted(
                                {
                                    f"{documents[doc]} ({dose} {frequency})".strip()
                                    for doc, dose, frequency in entries
                                }
                            )
                        )
                        + ". May reflect an intentional treatment change; verify dates.",
                    }
                )
        return {
            "is_multi_doc": len(documents) > 1,
            "document_count": len(documents),
            "documents": list(documents.values()),
            "contradictions": variations,
        }


multi_doc_synthesizer = MultiDocumentSynthesizer()
