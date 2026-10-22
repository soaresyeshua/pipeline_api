# -*- coding: utf-8 -*-
"""
LIVRO-RAZÃO IMUTÁVEL DE AUDITORIA (ENCADEAMENTO CRIPTOGRÁFICO DE HASHES)
=======================================================================
Garante registro pericial contra qualquer acusação de vazamento ou adulteração.
Cada evento é encadeado ao hash do evento anterior (estilo Blockchain/Merkle).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class EntradaAuditoria:
    id_entrada: str
    sequencia: int
    timestamp_utc: str
    ator: str  # ADVOGADO, ASSISTENTE_TECNICO, SISTEMA, IA
    acao: str  # EMISSAO_GRANT, ACESSO_DOC, REVOGACAO, etc.
    cnj: Optional[str]
    hash_documento: Optional[str]
    status: str
    hash_anterior: str
    hash_atual: str = ""
    detalhes: Dict[str, Any] = field(default_factory=dict)

    def calcular_hash(self) -> str:
        payload = {
            "id_entrada": self.id_entrada,
            "sequencia": self.sequencia,
            "timestamp_utc": self.timestamp_utc,
            "ator": self.ator,
            "acao": self.acao,
            "cnj": self.cnj,
            "hash_documento": self.hash_documento,
            "status": self.status,
            "hash_anterior": self.hash_anterior,
            "detalhes": self.detalhes,
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


class LivroRazaoAuditoria:
    GENESIS = "0" * 64

    def __init__(self) -> None:
        self._entradas: List[EntradaAuditoria] = []
        self._ultimo_hash = self.GENESIS

    def registrar(
        self, ator: str, acao: str, cnj: Optional[str] = None, hash_documento: Optional[str] = None, status: str = "SUCESSO", detalhes: Optional[Dict[str, Any]] = None
    ) -> EntradaAuditoria:
        agora = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        seq = len(self._entradas) + 1
        e = EntradaAuditoria(
            id_entrada=str(uuid.uuid4()),
            sequencia=seq,
            timestamp_utc=agora,
            ator=ator,
            acao=acao,
            cnj=cnj,
            hash_documento=hash_documento,
            status=status,
            hash_anterior=self._ultimo_hash,
            detalhes=detalhes or {},
        )
        e.hash_atual = e.calcular_hash()
        self._ultimo_hash = e.hash_atual
        self._entradas.append(e)
        return e

    def verificar_integridade(self) -> Tuple[bool, List[str]]:
        esperado_prev = self.GENESIS
        erros: List[str] = []
        for e in self._entradas:
            if e.hash_anterior != esperado_prev:
                erros.append(f"Cadeia rompida na entrada {e.sequencia}.")
            if e.calcular_hash() != e.hash_atual:
                erros.append(f"Conteúdo adulterado na entrada {e.sequencia}.")
            esperado_prev = e.hash_atual
        return len(erros) == 0, erros
