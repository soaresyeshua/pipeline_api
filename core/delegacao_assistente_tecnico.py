# -*- coding: utf-8 -*-
"""
MÓDULO DE DELEGAÇÃO DE ACESSO PARA ASSISTENTES TÉCNICOS (AT)
============================================================
PRINCÍPIO DE SEGURANÇA MANDATÓRIO:
O Assistente Técnico NUNCA recebe a senha, o certificado A1 (.pfx)
nem o cookie de sessão do Advogado.

O Advogado seleciona o processo (CNJ) do seu overview e autoriza o AT.
O sistema gera um Token Efêmero assinado internamente (HMAC-SHA256).
O AT acessa apenas as peças autorizadas, com revogação imediata em O(1).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class StatusAutorizacao(str, Enum):
    ATIVA = "ATIVA"
    REVOGADA = "REVOGADA"
    EXPIRADA = "EXPIRADA"


@dataclass
class RegrasEscopoDocumental:
    """Delimita com precisão quais tipos de documentos o AT pode acessar."""
    tipos_documentos_permitidos: List[str] = field(default_factory=lambda: ["*"])
    data_limite_juntada_utc: Optional[str] = None
    permitir_binarios_brutos: bool = False
    ocultar_dados_financeiros_seguradora: bool = True

    def documento_permitido(self, tipo_doc: str, data_juntada_utc: Optional[str] = None) -> bool:
        if "*" not in self.tipos_documentos_permitidos:
            tipo_limpo = (tipo_doc or "").strip().upper()
            permitidos = [t.strip().upper() for t in self.tipos_documentos_permitidos]
            if tipo_limpo not in permitidos:
                return False
        if self.data_limite_juntada_utc and data_juntada_utc:
            if data_juntada_utc > self.data_limite_juntada_utc:
                return False
        return True


@dataclass
class AutorizacaoProcesso:
    """Autorização explícita, auditável e revogável emitida pelo Advogado."""
    id_autorizacao: str
    cnj: str
    advogado_cpf: str
    advogado_oab: str
    advogado_nome: str
    assistente_tecnico_id: str
    assistente_tecnico_nome: str
    assistente_tecnico_registro: str  # Ex: CRC, CRM, CREA, CORECON
    finalidade: str
    regras_escopo: RegrasEscopoDocumental
    criado_em_utc: str
    expira_em_utc: str
    status: StatusAutorizacao = StatusAutorizacao.ATIVA
    revogado_em_utc: Optional[str] = None
    revogado_por: Optional[str] = None
    motivo_revogacao: Optional[str] = None
    selo_criptografico_sha256: str = ""

    def calcular_payload_canonico(self) -> Dict[str, Any]:
        return {
            "id_autorizacao": self.id_autorizacao,
            "cnj": self.cnj,
            "advogado_cpf": self.advogado_cpf,
            "advogado_oab": self.advogado_oab,
            "advogado_nome": self.advogado_nome,
            "assistente_tecnico_id": self.assistente_tecnico_id,
            "assistente_tecnico_nome": self.assistente_tecnico_nome,
            "assistente_tecnico_registro": self.assistente_tecnico_registro,
            "finalidade": self.finalidade,
            "regras_escopo": asdict(self.regras_escopo),
            "criado_em_utc": self.criado_em_utc,
            "expira_em_utc": self.expira_em_utc,
        }

    def selar(self) -> str:
        payload = self.calcular_payload_canonico()
        canonical_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.selo_criptografico_sha256 = hashlib.sha256(canonical_bytes).hexdigest()
        return self.selo_criptografico_sha256

    def verificar_integridade(self) -> bool:
        if not self.selo_criptografico_sha256:
            return False
        payload = self.calcular_payload_canonico()
        canonical_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        esperado = hashlib.sha256(canonical_bytes).hexdigest()
        return hmac.compare_digest(self.selo_criptografico_sha256, esperado)

    def esta_valida(self, agora: Optional[datetime] = None) -> Tuple[bool, str]:
        agora_dt = agora or datetime.now(UTC)
        if not self.verificar_integridade():
            return False, "AUTORIZACAO_ADULTERADA_HASH_INVALIDO"
        if self.status == StatusAutorizacao.REVOGADA:
            return False, f"AUTORIZACAO_REVOGADA: {self.motivo_revogacao or 'Sem motivo especificado'}"
        if self.status != StatusAutorizacao.ATIVA:
            return False, f"STATUS_INVALIDO: {self.status.value}"
        try:
            exp = datetime.fromisoformat(self.expira_em_utc)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=UTC)
            if agora_dt > exp:
                return False, "AUTORIZACAO_EXPIRADA"
        except (ValueError, TypeError):
            return False, "TIMESTAMP_EXPIRACAO_INVALIDO"
        return True, "VALIDA"

    def revogar(self, revogado_por: str, motivo: str, agora: Optional[datetime] = None) -> None:
        agora_dt = agora or datetime.now(UTC)
        self.status = StatusAutorizacao.REVOGADA
        self.revogado_em_utc = agora_dt.isoformat().replace("+00:00", "Z")
        self.revogado_por = revogado_por
        self.motivo_revogacao = motivo


@dataclass
class TokenAcessoAssistenteTecnico:
    """Token efêmero entregue ao Assistente Técnico (Sem credencial do advogado)."""
    id_token: str
    id_autorizacao: str
    assistente_tecnico_id: str
    cnj: str
    emitido_em_utc: str
    expira_em_utc: str
    assinatura_hmac: str

    @classmethod
    def criar(
        cls, autorizacao: AutorizacaoProcesso, chave_mestra_secreta: str, ttl_segundos: int = 3600
    ) -> TokenAcessoAssistenteTecnico:
        agora_dt = datetime.now(UTC)
        exp_dt = agora_dt + timedelta(seconds=ttl_segundos)
        id_token = str(uuid.uuid4())
        emitido_em = agora_dt.isoformat().replace("+00:00", "Z")
        expira_em = exp_dt.isoformat().replace("+00:00", "Z")

        mensagem = f"{id_token}:{autorizacao.id_autorizacao}:{autorizacao.assistente_tecnico_id}:{autorizacao.cnj}:{expira_em}"
        assinatura = hmac.new(chave_mestra_secreta.encode("utf-8"), mensagem.encode("utf-8"), hashlib.sha256).hexdigest()

        return cls(
            id_token=id_token,
            id_autorizacao=autorizacao.id_autorizacao,
            assistente_tecnico_id=autorizacao.assistente_tecnico_id,
            cnj=autorizacao.cnj,
            emitido_em_utc=emitido_em,
            expira_em_utc=expira_em,
            assinatura_hmac=assinatura,
        )

    def verificar(self, chave_mestra_secreta: str, agora: Optional[datetime] = None) -> Tuple[bool, str]:
        agora_dt = agora or datetime.now(UTC)
        try:
            exp = datetime.fromisoformat(self.expira_em_utc)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=UTC)
            if agora_dt > exp:
                return False, "TOKEN_EXPIRADO"
        except Exception:
            return False, "EXPIRACAO_INVALIDA"

        mensagem = f"{self.id_token}:{self.id_autorizacao}:{self.assistente_tecnico_id}:{self.cnj}:{self.expira_em_utc}"
        esperado = hmac.new(chave_mestra_secreta.encode("utf-8"), mensagem.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(self.assinatura_hmac, esperado):
            return False, "ASSINATURA_HMAC_INVALIDA"
        return True, "VALIDO"


class ServicoPermissoes:
    """Gerencia e valida autorizações, tokens efêmeros e filtragem de acervo."""
    def __init__(self, chave_mestra: Optional[str] = None):
        self.chave_mestra = chave_mestra or secrets.token_hex(32)
        self._autorizacoes: Dict[str, AutorizacaoProcesso] = {}

    def emitir_autorizacao(
        self,
        cnj: str,
        advogado_cpf: str,
        advogado_oab: str,
        advogado_nome: str,
        assistente_tecnico_id: str,
        assistente_tecnico_nome: str,
        assistente_tecnico_registro: str,
        finalidade: str,
        regras_escopo: Optional[RegrasEscopoDocumental] = None,
        ttl_dias: int = 30,
    ) -> AutorizacaoProcesso:
        agora = datetime.now(UTC)
        expira = agora + timedelta(days=ttl_dias)
        aut = AutorizacaoProcesso(
            id_autorizacao=str(uuid.uuid4()),
            cnj=cnj,
            advogado_cpf=advogado_cpf,
            advogado_oab=advogado_oab,
            advogado_nome=advogado_nome,
            assistente_tecnico_id=assistente_tecnico_id,
            assistente_tecnico_nome=assistente_tecnico_nome,
            assistente_tecnico_registro=assistente_tecnico_registro,
            finalidade=finalidade,
            regras_escopo=regras_escopo or RegrasEscopoDocumental(),
            criado_em_utc=agora.isoformat().replace("+00:00", "Z"),
            expira_em_utc=expira.isoformat().replace("+00:00", "Z"),
            status=StatusAutorizacao.ATIVA,
        )
        aut.selar()
        self._autorizacoes[aut.id_autorizacao] = aut
        return aut

    def revogar_autorizacao(self, id_autorizacao: str, revogado_por: str, motivo: str) -> bool:
        aut = self._autorizacoes.get(id_autorizacao)
        if not aut:
            return False
        aut.revogar(revogado_por=revogado_por, motivo=motivo)
        return True

    def emitir_token_at(self, id_autorizacao: str, ttl_segundos: int = 3600) -> Optional[TokenAcessoAssistenteTecnico]:
        aut = self._autorizacoes.get(id_autorizacao)
        if not aut:
            return None
        valido, _ = aut.esta_valida()
        if not valido:
            return None
        return TokenAcessoAssistenteTecnico.criar(aut, self.chave_mestra, ttl_segundos=ttl_segundos)

    def validar_requisicao_at(self, token: TokenAcessoAssistenteTecnico, cnj_solicitado: str) -> Tuple[bool, Optional[AutorizacaoProcesso], str]:
        token_valido, motivo_tok = token.verificar(self.chave_mestra)
        if not token_valido:
            return False, None, motivo_tok

        aut = self._autorizacoes.get(token.id_autorizacao)
        if not aut:
            return False, None, "AUTORIZACAO_NAO_ENCONTRADA"

        if aut.cnj != cnj_solicitado:
            return False, None, "ACESSO_BLOQUEADO_CNJ_DIFERENTE_DO_AUTORIZADO"

        aut_valida, motivo_aut = aut.esta_valida()
        if not aut_valida:
            return False, None, motivo_aut

        return True, aut, "ACESSO_LIBERADO"

    def filtrar_acervo_para_at(self, autorizacao: AutorizacaoProcesso, lista_documentos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove peças sigilosas e binários caso não explicitamente concedidos."""
        liberados: List[Dict[str, Any]] = []
        for doc in lista_documentos:
            tipo = doc.get("tipo", "ANEXO")
            data = doc.get("data_juntada")
            if not autorizacao.regras_escopo.documento_permitido(tipo, data):
                continue
            doc_limpo = dict(doc)
            if not autorizacao.regras_escopo.permitir_binarios_brutos and "binario" in doc_limpo:
                del doc_limpo["binario"]
            liberados.append(doc_limpo)
        return liberados
