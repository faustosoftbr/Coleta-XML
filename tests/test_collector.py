import os
import shutil
import zipfile
import unittest
from pathlib import Path

from src.xml_parser import (
    extract_key_from_filename,
    parse_key_metadata,
    parse_inut_xml,
    clean_digits
)
from src.sequence import analyze_sequences
from src.collector import CollectorEngine

def make_chave(uf="50", aamm="2610", cnpj="12345678000195", mod="65", serie=11, num=17155):
    return f"{uf}{aamm}{cnpj}{mod}{serie:03d}{num:09d}1123456780"

SAMPLE_NFE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc versao="4.00" xmlns="http://www.portalfiscal.inf.br/nfe">
    <NFe>
        <infNFe Id="NFe{chave}" versao="4.00">
            <ide>
                <mod>{mod}</mod>
                <serie>{serie}</serie>
                <nNF>{nnf}</nNF>
                <dhEmi>{dhemi}</dhEmi>
            </ide>
            <emit>
                <CNPJ>{cnpj}</CNPJ>
                <xNome>EMPRESA TESTE LTDA</xNome>
            </emit>
            <total>
                <ICMSTot>
                    <vNF>{valor:.2f}</vNF>
                </ICMSTot>
            </total>
        </infNFe>
    </NFe>
    <protNFe versao="4.00">
        <infProt>
            <dhRecbto>{dhrecbto}</dhRecbto>
            <nProt>150260397550812</nProt>
            <cStat>100</cStat>
            <xMotivo>Autorizado o uso da NF-e</xMotivo>
        </infProt>
    </protNFe>
</nfeProc>
"""

class TestAuthorizationDateCollector(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_sandbox")
        self.src_dir = self.test_dir / "origem"
        self.dest_dir = self.test_dir / "destino"
        
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            
        self.src_dir.mkdir(parents=True, exist_ok=True)
        self.dest_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_authorization_date_boundary_rules(self):
        # 1. Nota regular de Outubro: emitida e autorizada em 15/10/2026 (num 100)
        ch_out = make_chave(aamm="2610", num=100)
        p_out = self.src_dir / f"{ch_out}.xml"
        with open(p_out, "w", encoding="utf-8") as f:
            f.write(SAMPLE_NFE_XML.format(
                chave=ch_out, mod="65", serie=11, nnf=100,
                dhemi="2026-10-15T10:00:00-04:00",
                dhrecbto="2026-10-15T10:00:05-04:00",
                cnpj="12345678000195", valor=100.0
            ))

        # 2. Exemplo exato do usuário:
        # Emitida em 01/11 (AAMM=2611), mas AUTORIZADA em 31/10/2026 23:30 (num 101)
        ch_nov = make_chave(aamm="2611", num=101)
        p_nov = self.src_dir / f"{ch_nov}.xml"
        with open(p_nov, "w", encoding="utf-8") as f:
            f.write(SAMPLE_NFE_XML.format(
                chave=ch_nov, mod="65", serie=11, nnf=101,
                dhemi="2026-11-01T00:30:03-03:00",
                dhrecbto="2026-10-31T23:30:03-04:00",
                cnpj="12345678000195", valor=250.0
            ))

        # 3. Nota emitida em 31/10 mas AUTORIZADA em 01/11 (num 102) -> Deve sair de Outubro
        ch_virada = make_chave(aamm="2610", num=102)
        p_virada = self.src_dir / f"{ch_virada}.xml"
        with open(p_virada, "w", encoding="utf-8") as f:
            f.write(SAMPLE_NFE_XML.format(
                chave=ch_virada, mod="65", serie=11, nnf=102,
                dhemi="2026-10-31T23:55:00-03:00",
                dhrecbto="2026-11-01T00:05:00-04:00",
                cnpj="12345678000195", valor=300.0
            ))

        # 4. Nota de Novembro distante (dia 05/11) -> Ignorada
        ch_nov_longe = make_chave(aamm="2611", num=103)
        p_nov_longe = self.src_dir / f"{ch_nov_longe}.xml"
        with open(p_nov_longe, "w", encoding="utf-8") as f:
            f.write(SAMPLE_NFE_XML.format(
                chave=ch_nov_longe, mod="65", serie=11, nnf=103,
                dhemi="2026-11-05T14:00:00-03:00",
                dhrecbto="2026-11-05T14:00:05-03:00",
                cnpj="12345678000195", valor=50.0
            ))

        engine = CollectorEngine(
            source_paths=[str(self.src_dir)],
            destination_path=str(self.dest_dir),
            cnpjs=["12.345.678/0001-95"],
            target_month="10",
            target_year="2026",
            filter_nfe=True,
            filter_nfce=True,
            generate_zip=True
        )

        engine.start()
        engine.thread.join(timeout=10)

        # Verifica ZIP gerado
        zips = list(self.dest_dir.glob("*.zip"))
        self.assertEqual(len(zips), 1)

        with zipfile.ZipFile(zips[0], "r") as zf:
            namelist = zf.namelist()
            xmls = [n for n in namelist if n.endswith(".xml")]

            # Devem estar no ZIP de Outubro:
            # - Nota 100 (emitida 15/10, autorizada 15/10)
            # - Nota 101 (emitida 01/11, mas AUTORIZADA 31/10)
            # NÃO devem estar:
            # - Nota 102 (autorizada 01/11)
            # - Nota 103 (autorizada 05/11)
            self.assertEqual(len(xmls), 2, f"Esperava 2 notas em Outubro, encontrou {len(xmls)}: {xmls}")
            
            # Verifica que a nota 101 (do dia 01/11 com autorização 31/10) está presente no ZIP de Outubro!
            tem_nota_101 = any(ch_nov in n for n in xmls)
            self.assertTrue(tem_nota_101, "A nota 101 (autorizada em 31/10) deveria estar presente no ZIP!")

            txt = zf.read("relatorio_coleta.txt").decode("utf-8")
            self.assertIn("EMISSÃO", txt)
            self.assertIn("AUTORIZAÇÃO", txt)
            self.assertIn("31/10/2026 23:30", txt)

if __name__ == "__main__":
    unittest.main()
