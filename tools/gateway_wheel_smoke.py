"""Run outside the checkout against an installed wheel; generated local XML only."""
import json
import tempfile
from pathlib import Path

from click.testing import CliRunner

import pa_cli
from pa_cli.cli import main
from pa_cli.gateway import PaperEvaluationCandidate, evaluate_gateway_request
from pa_cli.gateway_store import GatewayStore


def run():
    assert pa_cli.__version__ == "4.0.0"
    with tempfile.TemporaryDirectory(prefix="gateway-wheel-") as directory:
        root = Path(directory)
        artifact = root / "generated.xml"
        artifact.write_text(
            '<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta>'
            '<article-id pub-id-type="doi">10.1000/wheel-fixture</article-id>'
            '<title-group><article-title>Generated fixture</article-title></title-group>'
            '<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/"/>'
            '</permissions></article-meta></front><body><p>Generated evidence passage.</p>'
            '</body></article>', encoding="utf-8")
        ledger = root / "journal.sqlite3"
        receipt, _ = evaluate_gateway_request("wheel-run", "wheel-test",
            [PaperEvaluationCandidate("fixture", str(artifact), "10.1000/wheel-fixture",
                                      source="pmc_xml", url="https://eutils.ncbi.nlm.nih.gov")],
            ["Generated evidence passage."], True, True, audit_file=root / "audit.jsonl",
            ledger_file=ledger, verify_passage_provenance=True)
        assert receipt.gateway_decision == "AUTHORIZED", receipt.rejection_reasons
        assert receipt.provenance_verified
        with GatewayStore(ledger, read_only=True, create=False) as store:
            assert store.receipts() == [receipt.to_dict()]
            assert store.status()["pending"] == []
            assert store.status()["runs"][0]["papers"] == 1
        result = CliRunner().invoke(main, ["gateway", "doctor", "--ledger", str(ledger), "--json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["integrity"] == "ok"
    print("Installed v4 gateway wheel smoke test passed")


if __name__ == "__main__":
    run()
