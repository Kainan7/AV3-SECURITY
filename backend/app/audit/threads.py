# app/audit/threads.py
from __future__ import annotations

"""
Barramento de Auditoria (Producer/Consumer com Thread)

Por que existe?
- Rotas FastAPI não devem ficar fazendo I/O de disco (log) em cada request,
  porque isso aumenta latência e pode travar a API em pico.
- A solução é Producer/Consumer:
  - Producers enfileiram eventos rapidamente (FIFO).
  - Uma thread dedicada consome e executa o handler (persistência, SSE futuro, etc.).

Benefícios:
- performance (requisição não espera escrita em disco)
- ordenação (FIFO preserva a ordem temporal)
- robustez (erros no handler não derrubam a API)
"""

import queue
import threading
from typing import Callable, Optional

from app.audit.modelos import EventoAuditoria


class BarramentoAuditoria:
    """
    Fila + Thread consumidora.

    Fluxo:
    - publicar(evento) -> coloca na fila (rápido)
    - worker -> consome fila e chama handler(evento)
    """

    def __init__(
        self,
        handler: Callable[[EventoAuditoria], None],
        tamanho_max_fila: int = 10_000,
        nome_worker: str = "auditoria-writer",
    ):
        """
        handler:
            Função executada para cada evento consumido.
            Ex.: persistir_evento(evento) em JSONL.

        tamanho_max_fila:
            Limite da fila para proteger memória em situações de pico.

        nome_worker:
            Nome amigável da thread (ajuda debugging).
        """
        self._handler = handler
        self._fila: queue.Queue[EventoAuditoria] = queue.Queue(maxsize=tamanho_max_fila)

        self._parar = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._nome_worker = nome_worker

    # -------------------------------------------------
    # Controle do Worker
    # -------------------------------------------------
    def iniciar(self) -> None:
        """
        Inicia a thread consumidora (idempotente).

        Por que idempotente?
        - Evita criar duas threads por engano em reload/dev.
        """
        if self._thread and self._thread.is_alive():
            return

        self._parar.clear()
        self._thread = threading.Thread(
            target=self._loop_consumidor,
            name=self._nome_worker,
            daemon=True,  # Em DEV: encerra junto com o processo
        )
        self._thread.start()

    def parar(self, timeout: float = 2.0) -> None:
        """
        Solicita parada e aguarda a thread encerrar.

        Observação:
        - Em produção, você pode querer drenar a fila antes de parar,
          mas para o projeto atual, join com timeout já resolve.
        """
        self._parar.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    # -------------------------------------------------
    # API do Producer (rotas/services)
    # -------------------------------------------------
    def publicar(self, evento: EventoAuditoria, timeout: float = 0.5) -> bool:
        """
        Enfileira um evento na fila (FIFO).

        Por que tem timeout?
        - Para uma request não ficar travada se a fila estiver cheia.

        Retorna:
        - True: enfileirou
        - False: fila cheia (evento descartado para proteger a API)
        """
        try:
            self._fila.put(evento, timeout=timeout)
            return True
        except queue.Full:
            return False

    # -------------------------------------------------
    # Loop do Consumer (Thread)
    # -------------------------------------------------
    def _loop_consumidor(self) -> None:
        """
        Loop da thread consumidora.

        Regras:
        - Não deixar exceção matar a thread.
        - Consumir rápido e processar via handler.
        """
        while not self._parar.is_set():
            try:
                # Timeout pequeno para permitir verificar self._parar periodicamente
                evento = self._fila.get(timeout=0.25)
            except queue.Empty:
                continue

            try:
                self._handler(evento)
            except Exception:
                # Importante: erro no handler NÃO pode matar o worker.
                # Se quiser, depois adicionamos fallback (ex.: escrever em stderr).
                pass
            finally:
                self._fila.task_done()
