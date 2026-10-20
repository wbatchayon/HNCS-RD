# -*- coding: utf-8 -*-
"""Analyse syntaxique de tous les scripts PowerShell du dépôt (spec § 12).

Utilise `powershell` (Windows PowerShell 5.1) s'il est présent, sinon `pwsh`. Avec `pwsh`, les jetons
propres à PowerShell 7 (`??`, `?.`, ternaire, `&&`, `||`) sont signalés, afin de garantir la même
compatibilité « parseur 5.1 » que sous Windows. Test sauté si aucun interpréteur n'est disponible.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from hncs_offline import ROOT

EXCLUDED_DIRS = {".git", "node_modules", "dist", "build", "__pycache__"}
SHELL = shutil.which("powershell") or shutil.which("pwsh")

PARSE_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$files = Get-Content -LiteralPath $env:HNCS_PS_LIST -Encoding UTF8
$ps7Only = @('QuestionQuestion','QuestionQuestionEquals','QuestionDot','QuestionLBracket','AndAnd','OrOr','QuestionMark')
$out = foreach ($f in $files) {
    if (-not $f) { continue }
    $tokens = $null; $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($f, [ref]$tokens, [ref]$errors)
    $msgs = @()
    foreach ($e in $errors) { $msgs += ('{0}:{1} {2}' -f $e.Extent.StartLineNumber, $e.Extent.StartColumnNumber, $e.Message) }
    foreach ($t in $tokens) {
        if ($ps7Only -contains $t.Kind.ToString()) { $msgs += ('{0}:{1} operateur PowerShell 7 uniquement : {2}' -f $t.Extent.StartLineNumber, $t.Extent.StartColumnNumber, $t.Text) }
    }
    [pscustomobject]@{ File = [string]$f; Errors = @($msgs) }
}
$json = ConvertTo-Json -InputObject @($out) -Depth 4 -Compress
[System.IO.File]::WriteAllText($env:HNCS_PS_OUT, $json, (New-Object System.Text.UTF8Encoding($false)))
"""


def powershell_files() -> list[Path]:
    out = []
    for p in ROOT.rglob("*"):
        if p.suffix.lower() in (".ps1", ".psm1", ".psd1") and p.is_file():
            if not EXCLUDED_DIRS & set(p.relative_to(ROOT).parts):
                out.append(p)
    return sorted(out)


@unittest.skipUnless(SHELL, "ni powershell ni pwsh disponible")
class TestSyntaxePowerShell(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = [p for p in powershell_files() if p.suffix.lower() != ".psd1"]
        cls.results = {}
        if not cls.files:
            return
        with tempfile.TemporaryDirectory() as tmp:
            lst = Path(tmp) / "files.txt"
            res = Path(tmp) / "result.json"
            lst.write_text("\n".join(str(p) for p in cls.files), encoding="utf-8")
            env = dict(os.environ, HNCS_PS_LIST=str(lst), HNCS_PS_OUT=str(res))
            proc = subprocess.run([SHELL, "-NoProfile", "-NonInteractive", "-Command", PARSE_SCRIPT],
                                  capture_output=True, env=env, timeout=300)
            if proc.returncode != 0 or not res.exists():
                raise RuntimeError("analyse PowerShell impossible : " + proc.stderr.decode("utf-8", "replace"))
            data = json.loads(res.read_text(encoding="utf-8-sig") or "[]")
            for r in data if isinstance(data, list) else [data]:
                cls.results[str(Path(r["File"]).resolve())] = r["Errors"] or []

    def test_scripts_analysables(self):
        if not self.files:
            self.skipTest("aucun script PowerShell")
        for p in self.files:
            with self.subTest(fichier=str(p.relative_to(ROOT))):
                errs = self.results.get(str(p.resolve()))
                self.assertIsNotNone(errs, "fichier non analysé")
                self.assertEqual(errs, [], "\n".join(errs))


class TestEncodagePowerShell(unittest.TestCase):
    # Périmètre de la règle : scripts du jeu de test et des tests (exécutables sous 5.1 comme sous 7).
    # Les autres dossiers ciblent PowerShell 7.4, qui lit l'UTF-8 sans BOM ; leur analyse 5.1 est couverte ci-dessus.
    SCOPE = ("testdata", "tests")

    def test_bom_si_caracteres_non_ascii(self):
        """Windows PowerShell 5.1 lit un fichier sans BOM en ANSI : un fichier non ASCII doit avoir un BOM UTF-8."""
        files = [p for p in powershell_files() if p.relative_to(ROOT).parts[0] in self.SCOPE]
        if not files:
            self.skipTest("aucun script PowerShell")
        for p in files:
            raw = p.read_bytes()
            with self.subTest(fichier=str(p.relative_to(ROOT))):
                if raw.startswith(b"\xef\xbb\xbf"):
                    continue
                try:
                    raw.decode("ascii")
                except UnicodeDecodeError:
                    self.fail("caractères non ASCII sans BOM UTF-8 (mal lus par Windows PowerShell 5.1)")


if __name__ == "__main__":
    unittest.main()
