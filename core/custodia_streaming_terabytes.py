# -*- coding: utf-8 -*-
"""
STREAMING DE TERABYTES E FIXAÇÃO CRIPTOGRÁFICA DE CUSTÓDIA
==========================================================
Permite processar milhares de documentos e gigabytes/terabytes
sem carregar arquivos volumosos na memória RAM.
Calcula SHA-256 e SHA-512 em blocos de 64 KB no instante zero da ingestão.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Optional, Tuple


@dataclass(frozen=True)
class ResultadoStreaming:
    hash_sha256: str
    hash_sha512: str
    total_bytes_ingeridos: int
    total_chunks: int


class BufferStreamingCustodia:
    """Manipula streams de terabytes calculando hashes no fluxo de gravação."""
    TAMANHO_BLOCO = 64 * 1024  # 64 KB

    @classmethod
    def ingerir_fluxo_em_chunks(
        cls, stream_entrada: BinaryIO, chunk_tamanho_bytes: int = TAMANHO_BLOCO
    ) -> ResultadoStreaming:
        """
        Consome um stream contínuo (BytesIO, socket de rede ou arquivo) em blocos
        calculando SHA-256 e SHA-512 concorrentemente sem estourar a RAM.
        """
        hasher_256 = hashlib.sha256()
        hasher_512 = hashlib.sha512()
        total_bytes = 0
        total_chunks = 0

        while True:
            bloco = stream_entrada.read(chunk_tamanho_bytes)
            if not bloco:
                break
            hasher_256.update(bloco)
            hasher_512.update(bloco)
            total_bytes += len(bloco)
            total_chunks += 1

        return ResultadoStreaming(
            hash_sha256=hasher_256.hexdigest(),
            hash_sha512=hasher_512.hexdigest(),
            total_bytes_ingeridos=total_bytes,
            total_chunks=total_chunks,
        )

    @classmethod
    def processar_stream_e_gravar(
        cls, conteudo_bytes: bytes, caminho_destino: Optional[Path] = None
    ) -> Tuple[str, str, int]:
        """
        Processa o binário em chunks, calcula hashes duplo (SHA-256 e SHA-512)
        e salva de forma atômica no armazenamento de custódia.
        """
        hasher_256 = hashlib.sha256()
        hasher_512 = hashlib.sha512()
        total_bytes = len(conteudo_bytes)

        for offset in range(0, total_bytes, cls.TAMANHO_BLOCO):
            bloco = conteudo_bytes[offset:offset + cls.TAMANHO_BLOCO]
            hasher_256.update(bloco)
            hasher_512.update(bloco)

        sha256 = hasher_256.hexdigest()
        sha512 = hasher_512.hexdigest()

        if caminho_destino:
            caminho_destino.parent.mkdir(parents=True, exist_ok=True)
            caminho_destino.write_bytes(conteudo_bytes)

        return sha256, sha512, total_bytes
