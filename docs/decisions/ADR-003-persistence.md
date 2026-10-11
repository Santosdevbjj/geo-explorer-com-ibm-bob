# ADR-003 — Persistência de alertas

- **Status:** Aceito para a versão de portfólio; revisar antes de produção.
- **Contexto:** A API mantém alertas em memória. Reinicializações e ambientes serverless podem perder os registros.
- **Decisão:** manter o armazenamento em memória na demonstração inicial e documentar explicitamente que não oferece persistência durável. Não introduzir SQLite como se fosse persistência válida em uma plataforma com filesystem efêmero.
- **Alternativas:** SQLite local para desenvolvimento; serviço de banco gerenciado para produção; fila/event store para arquiteturas com maior volume.
- **Consequências:** setup simples e reproduzível; alertas desaparecem quando o processo reinicia; não há garantias de concorrência, durabilidade ou auditoria de produção.
- **Gatilho para rever:** necessidade comprovada de consulta histórica, múltiplas réplicas, trilha de auditoria ou SLA.
