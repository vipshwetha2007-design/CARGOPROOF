import asyncio
import sys

from .verifier import verify_shipment

SOURCE_LABELS = {
    "shipment": "Shipment",
    "vessel_tracking": "Vessel",
    "container_registry": "Container",
    "port_records": "Port Records",
    "gps": "GPS",
    "inspection": "Inspection",
    "shipment_documents": "Documents",
}


async def _run(shipment_id: str) -> None:
    print("=" * 40)
    print("CargoProof Verification Engine")
    print("=" * 40)
    print()
    print(f"Shipment: {shipment_id}")
    print()
    print("Collecting evidence...")
    print()

    report = await verify_shipment(shipment_id)

    for key, label in SOURCE_LABELS.items():
        mark = "\u2713" if key in report.evidence_sources else "\u2717"
        print(f"{mark} {label}")

    print()
    print("Running verification...")
    print()
    print("-" * 40)
    print("RESULT")
    print("-" * 40)
    print(f"Status     : {report.verification_status}")
    print(f"Confidence : {report.confidence_score}%")
    print(f"Decision   : {report.decision}")
    print()
    print("Evidence Hash:")
    print(report.evidence_hash)
    print()

    if report.failed_rules:
        print("Reasons:")
        for r in report.failed_rules:
            print(f"  - {r.message}")
        print()

    if report.warnings:
        print("Warnings:")
        for w in report.warnings:
            print(f"  - {w}")
        print()

    print("-" * 40)
    print("=" * 40)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m verification_engine.demo <SHIPMENT_ID>")
        sys.exit(1)
    asyncio.run(_run(sys.argv[1]))


if __name__ == "__main__":
    main()
