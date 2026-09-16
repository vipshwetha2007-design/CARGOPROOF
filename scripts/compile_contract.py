from pathlib import Path
from pyteal import compileTeal, Mode
from contracts.cargoproof_escrow import approval, clear

out = Path("contracts/build")
out.mkdir(parents=True, exist_ok=True)

(out / "approval.teal").write_text(
    compileTeal(
        approval(),
        Mode.Application,
        version=8
    )
)

(out / "clear.teal").write_text(
    compileTeal(
        clear(),
        Mode.Application,
        version=8
    )
)

print("Wrote contracts/build/approval.teal")
print("Wrote contracts/build/clear.teal")