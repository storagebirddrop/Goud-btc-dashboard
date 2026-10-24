"""HIST-12: the TypeScript gate (`frontend/src/hist.ts`, bundled with the project's own esbuild) must accept and refuse exactly what the Python contract does, on the SYNTHETIC
fixture set. Pure logic, no browser. Usage: python -m tests.hist12.gate_parity   (needs `npm ci` in frontend/; exit 0 only when every case agrees)"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from etl import hist_model as hm  # noqa: E402
from etl import hist_publication as hp  # noqa: E402
from tests.hist12 import fixtures as fx  # noqa: E402
from tests.hist12 import synthetic as sy  # noqa: E402

FRONTEND = ROOT / "frontend"
NODE_SCRIPT = """
import fs from 'node:fs';
import {activateHist} from './hist.mjs';
const dir = process.argv[2], names = JSON.parse(process.argv[3]), shas = JSON.parse(process.argv[4]), pins = JSON.parse(process.argv[5]);
const out = {};
const parse = b => { try { return JSON.parse(b.toString('utf8')); } catch { return undefined; } };
for (const n of names) {
  const b = fs.readFileSync(`${dir}/${n}.json`);
  const doc = parse(b);
  out[n] = {pinned_synth: !!activateHist(shas[n], doc, pins, true), pinned_prod: !!activateHist(shas[n], doc, pins, false),
            empty_pins: !!activateHist(shas[n], doc, [], true), wrong_hash: !!activateHist('0'.repeat(64), doc, pins, true), null_hash: !!activateHist(null, doc, pins, true)};
}
console.log(JSON.stringify(out));
"""


def available() -> bool:
    return (FRONTEND / "node_modules/.bin/esbuild").exists() and subprocess.run(["node", "--version"], capture_output=True).returncode == 0


def run() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        index = fx.build(tmp / "fixtures")
        subprocess.run([str(FRONTEND / "node_modules/.bin/esbuild"), str(FRONTEND / "src/hist.ts"), "--bundle", "--format=esm", f"--outfile={tmp / 'hist.mjs'}"], check=True, capture_output=True)
        (tmp / "run.mjs").write_text(NODE_SCRIPT)
        names = sorted(index["shas"])
        res = subprocess.run(["node", str(tmp / "run.mjs"), str(tmp / "fixtures"), json.dumps(names), json.dumps(index["shas"]), json.dumps(index["pinned"])], cwd=tmp, check=True, capture_output=True, text=True)
        ts = json.loads(res.stdout)
        # the Python verdict for the same fixtures: accepted only where the external record, the pin and the synthetic mode agree
        py = {}
        record_valid = sy.make_world(comparison=True)[1]
        record_nocmp = sy.make_world(comparison=False)[1]
        for n in names:
            blob = (tmp / "fixtures" / f"{n}.json").read_bytes()
            ok = False
            for rec, cmp_ok in ((record_valid, ("SYN-HIST-REL-1",)), (record_nocmp, ())):
                try:
                    hp.verify_payload(blob, pins=[hp.payload_sha256(blob)], records=[rec], comparison_releases=cmp_ok, production=False)
                    ok = True
                except hp.HistPublicationDenied:
                    pass
            py[n] = ok
        return {"ts": ts, "py": py, "names": names}


def main() -> int:
    if not available():
        print("NOT EXECUTED: node or frontend/node_modules (esbuild) missing")
        return 2
    r = run()
    bad = []
    for n in r["names"]:
        t = r["ts"][n]
        if t["pinned_synth"] != r["py"][n]:
            bad.append(f"{n}: TS {t['pinned_synth']} != Python {r['py'][n]}")
        if t["pinned_prod"] or t["empty_pins"] or t["wrong_hash"] or t["null_hash"]:
            bad.append(f"{n}: the gate opened in a mode that must stay closed {t}")
    accepted = sorted(n for n in r["names"] if r["ts"][n]["pinned_synth"])
    if accepted != ["valid", "valid_nocmp"]:
        bad.append(f"unexpected accepted set {accepted}")
    for line in bad:
        print("FAIL", line)
    print(f"gate parity: {len(r['names'])} fixtures, accepted {accepted}, {'MISMATCH' if bad else 'ALL AGREE'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
