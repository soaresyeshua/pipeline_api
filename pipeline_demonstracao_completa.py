# -*- coding: utf-8 -*-
"""
DEMONSTRAÇÃO DO PIPELINE INDUSTRIAL: DATAJUD, DJEN, STREAMING DE TERABYTES E CMAP
==================================================================================
Demonstra a esteira de alto desempenho para conexão de advogados aos tribunais:
1. Autenticação institucional do Advogado (sessão segura em memória volátil).
2. Emissão de autorização granular e Token Efêmero para o Assistente Técnico (AT).
3. Consulta oficial no DataJud CNJ e DJEN (Comunica PJe) com controle de vazão adaptativo.
4. Ingestão em streaming em blocos de 64 KB com cravamento duplo de hash (SHA-256 e SHA-512).
5. Decodificação tipográfica CMAP ToUnicode de PDFs judiciais em escala industrial.
6. Registro criptográfico imutável no Livro-Razão de Auditoria.
"""

import asyncio
import io

from core.auth_advogado_tribunal import AdvogadoSessao
from core.delegacao_assistente_tecnico import RegrasEscopoDocumental, ServicoPermissoes
from core.conector_datajud import ConectorDataJudCNJ
from core.conector_djen import ConectorDJEN
from core.conectores_datajud_djen import PacerAdaptativoVazao
from core.custodia_streaming_terabytes import BufferStreamingCustodia
from core.decodificador_cmap import normalizar_texto_cmap
from core.livro_razao_auditoria import LivroRazaoAuditoria


async def main():
    print("=" * 80)
    print("PIPELINE INDUSTRIAL DE DADOS JUDICIAIS: DATAJUD, DJEN, STREAMING E CMAP")
    print("=" * 80)

    # 1. Autenticação do Advogado (Zero-Storage em disco)
    print("\n[Passo 1] Autenticação do Advogado Constituído (Memória Volátil)...")
    sessao_adv = AdvogadoSessao(
        nome_advogado="DR. JOAO BATISTA",
        cpf_advogado="*************",
        oab_numero="445892",
        oab_uf="SP",
        bearer_token="JWT_OFICIAL_PDPJ_15MIN",
        jsession_id="SESSAO_PJE_ATIVA"
    )
    print(f"[+] Advogado Autenticado: {sessao_adv.nome_advogado} | OAB/{sessao_adv.oab_uf} {sessao_adv.oab_numero}")

    # 2. Concessão de Acesso ao Assistente Técnico (AT) Contratado
    print("\n[Passo 2] Concessão Granular de Acesso ao Assistente Técnico (AT)...")
    servico = ServicoPermissoes()
    ledger = LivroRazaoAuditoria()
    cnj = "5000537-06.2026.8.13.0116"

    autorizacao = servico.emitir_autorizacao(
        cnj=cnj,
        advogado_cpf=sessao_adv.cpf_advogado,
        advogado_oab=sessao_adv.oab_numero,
        advogado_nome=sessao_adv.nome_advogado,
        assistente_tecnico_id="AT_MARCELO",
        assistente_tecnico_nome="Marcelo Antônio Silveira",
        assistente_tecnico_registro="CRC-SP 189204/O-1",
        finalidade="ANALISE_DOCUMENTAL_DEFESA_TECNICA",
        regras_escopo=RegrasEscopoDocumental(
            tipos_documentos_permitidos=["PETICAO_INICIAL", "CONTESTACAO", "DOCUMENTO_PROBATÓRIO", "LAUDO_TECNICO"],
            permitir_binarios_brutos=False,
            ocultar_dados_financeiros_seguradora=True,
        )
    )
    token_at = servico.emitir_token_at(autorizacao.id_autorizacao)
    print(f"[+] Autorização Emitida: {autorizacao.id_autorizacao}")
    print(f"[+] Selo Criptográfico SHA-256: {autorizacao.selo_criptografico_sha256[:16]}...")
    print(f"[+] Token Efêmero do AT Emitido (Zero Vazamento de Sessão): {token_at.id_token}")

    ledger.registrar(ator="ADVOGADO", acao="EMISSAO_TOKEN_AT", cnj=cnj, status="CONCEDIDO")

    # 3. Consulta Oficial com Controle de Vazão (DataJud e DJEN)
    print("\n[Passo 3] Consultando as APIs Oficiais (DataJud CNJ e DJEN / Comunica PJe)...")
    pacer = PacerAdaptativoVazao(intervalo_minimo_segundos=0.01)
    conector_dj = ConectorDataJudCNJ(pacer=pacer)
    conector_djen = ConectorDJEN(pacer=pacer)

    res_datajud = await conector_dj.consultar_processo_cnj("TJMG", cnj)
    print(f"[+] DataJud CNJ: Classe='{res_datajud['dados_processuais']['classe']}' | Vara='{res_datajud['dados_processuais']['orgaoJulgador']}'")

    res_djen = await conector_djen.consultar_publicacoes(sigla_tribunal="TJMG", numero_processo_cnj=cnj)
    print(f"[+] DJEN (Comunica PJe): {res_djen['total_registros']} publicação(ões) retornada(s) em {res_djen['tempo_resposta_ms']} ms.")

    ledger.registrar(ator="CONECTOR_API", acao="CONSULTA_TRIBUNAL", cnj=cnj, status="SUCESSO")

    # 4. Ingestão em Streaming de Terabytes sem esgotar RAM
    print("\n[Passo 4] Ingestão em Streaming (Chunks de 64 KB com Hashing Duplo SHA-256 e SHA-512)...")
    bloco_simulado = b"CONTEUDO_BRUTO_DO_PROCESSO_JUDICIAL_EM_PDF_CHUNK_" * 2000  # ~100 KB
    stream_entrada = io.BytesIO(bloco_simulado)

    resultado_streaming = BufferStreamingCustodia.ingerir_fluxo_em_chunks(
        stream_entrada=stream_entrada,
        chunk_tamanho_bytes=65536
    )
    print(f"[+] Bytes Processados em Trânsito: {resultado_streaming.total_bytes_ingeridos} bytes")
    print(f"[+] Chunks Processados: {resultado_streaming.total_chunks}")
    print(f"[+] Hash SHA-256 do Fluxo: {resultado_streaming.hash_sha256}")
    print(f"[+] Hash SHA-512 do Fluxo: {resultado_streaming.hash_sha512[:32]}...")

    # 5. Decodificação CMap ToUnicode e Resolução de Ligaduras
    print("\n[Passo 5] Decodificação Tipográfica de PDFs com CMap ToUnicode...")
    texto_com_ligaduras = (
        "Conforme certid\u00e3o o\ufb01cial, a defesa t\u00e9cnica apresentou a mani-\n"
        "festa\u00e7\u00e3o e requereu a juntada de documentos para an\u00e1lise do assistente t\u00e9cnico."
    )
    texto_limpo, lig_resolvidas = normalizar_texto_cmap(texto_com_ligaduras)
    print(f"[+] Ligaduras Tipográficas Resolvidas: {lig_resolvidas}")
    print(f"[+] Texto Saneado: '{texto_limpo}'")

    ledger.registrar(ator="DECODIFICADOR_CMAP", acao="EXTRACAO_TEXTO", cnj=cnj, status="NORMALIZADO")

    # 6. Verificação do Livro-Razão de Auditoria
    integro, total = ledger.verificar_integridade()
    print(f"\n[Passo 6] Verificação do Livro-Razão Criptográfico ({total} eventos encadeados)...")
    print(f"[+] Integridade da Cadeia de Hash: {integro}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
