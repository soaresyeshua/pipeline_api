# -*- coding: utf-8 -*-
"""Suíte de testes de integração cobrindo DJEN, DataJud, CMap, Streaming e Delegação AT."""

import io
import pytest
from core.delegacao_assistente_tecnico import RegrasEscopoDocumental, ServicoPermissoes
from core.decodificador_cmap import normalizar_texto_cmap
from core.conector_djen import ConectorDJEN
from core.conector_datajud import ConectorDataJudCNJ
from core.custodia_streaming_terabytes import BufferStreamingCustodia
from core.livro_razao_auditoria import LivroRazaoAuditoria


def test_normalizador_cmap_e_ligaduras():
    texto_corrompido = "Conforme certid\u00e3o o\ufb01cial, a defesa juntou a mani-\nfesta\u00e7\u00e3o no prazo."
    limpo, resolvidas = normalizar_texto_cmap(texto_corrompido)
    assert resolvidas >= 1
    assert "oficial" in limpo
    assert "manifestação" in limpo


@pytest.mark.asyncio
async def test_conector_djen_consulta():
    conector = ConectorDJEN()
    res = await conector.consultar_publicacoes(sigla_tribunal="TJSP", numero_processo_cnj="5000537-06.2026.8.13.0116")
    assert res["status"] == 200
    assert len(res["comunicacoes"]) >= 1
    assert "defesa técnica" in res["comunicacoes"][0]["texto"].lower()


@pytest.mark.asyncio
async def test_conector_datajud_consulta():
    conector = ConectorDataJudCNJ()
    res = await conector.consultar_processo_cnj("TJMG", "5000537-06.2026.8.13.0116")
    assert res["status"] == 200
    assert "Procedimento Comum Cível" in res["dados_processuais"]["classe"]


def test_streaming_chunks_e_hashing_duplo():
    conteudo_simulado = b"BLOCO_DE_DADOS_PROCESSO_JUDICIAL_TERABYTES_" * 3000
    stream = io.BytesIO(conteudo_simulado)
    resultado = BufferStreamingCustodia.ingerir_fluxo_em_chunks(stream, chunk_tamanho_bytes=65536)
    assert resultado.total_bytes_ingeridos == len(conteudo_simulado)
    assert resultado.total_chunks > 1
    assert len(resultado.hash_sha256) == 64
    assert len(resultado.hash_sha512) == 128


def test_delegacao_at_e_revogacao_imediata():
    servico = ServicoPermissoes()
    aut = servico.emitir_autorizacao(
        cnj="5000537-06.2026.8.13.0116",
        advogado_cpf="00000000000",
        advogado_oab="445892",
        advogado_nome="Dr. Joao Batista",
        assistente_tecnico_id="AT_01",
        assistente_tecnico_nome="Marcelo",
        assistente_tecnico_registro="CRC",
        finalidade="ANALISE_DOCUMENTAL"
    )
    token = servico.emitir_token_at(aut.id_autorizacao)
    assert token is not None

    ok, _, _ = servico.validar_requisicao_at(token, "5000537-06.2026.8.13.0116")
    assert ok is True

    servico.revogar_autorizacao(aut.id_autorizacao, "ADVOGADO", "Revogacao imediata")
    ok_revogado, _, _ = servico.validar_requisicao_at(token, "5000537-06.2026.8.13.0116")
    assert ok_revogado is False


def test_livro_razao_encadeamento_hashes():
    ledger = LivroRazaoAuditoria()
    ledger.registrar("ADVOGADO", "LOGIN")
    ledger.registrar("AT", "ACESSO_DOC", hash_documento="abc")
    integro, erros = ledger.verificar_integridade()
    assert integro is True
    assert len(erros) == 0
