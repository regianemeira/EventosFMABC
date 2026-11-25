# Como o sistema roda em produção (VPS Hostinger)

Endereço: **https://eventos.appdigital.tech**

Desde novembro/2026 o sistema roda num VPS da Hostinger (Ubuntu), em Docker,
junto com outros sistemas da AppDigital. O Render e o Neon não são mais usados.

## Como está montado

```text
Internet ──HTTPS──> caddy (container)  ──>  eventos:8000 (container, Waitress + Flask)
                                                 │
                                                 └──> eventos-db (container, PostgreSQL 18)
```

| Peça | Onde fica |
|---|---|
| Proxy HTTPS (Caddy, certificados automáticos) | `/home/deploy/apps/proxy/` (`Caddyfile` + `docker-compose.yml`) |
| Compose do eventos (app + banco) | `/home/deploy/apps/eventos/docker-compose.yml` |
| Configurações e segredos | `/home/deploy/apps/eventos/.env` (fora do Git, permissão 600) |
| Código (cópia deste repositório) | `/home/deploy/apps/eventos/EventosFMABC/` |
| `Dockerfile` | dentro da pasta do código, **só no servidor** (não está no Git) |
| Dados do banco | volume Docker `eventos_pgdata` |
| Backups | `/root/backups-eventos/` |

- O container `eventos` só expõe a porta 8000 na rede interna do Docker. Quem
  acessa da internet passa sempre pelo Caddy.
- Todos os containers usam `restart: unless-stopped` e o Docker sobe com o
  servidor, então tudo volta sozinho depois de um `reboot`.
- O PostgreSQL instalado direto no Ubuntu (`postgresql@18-main`) **não** é usado
  pelo eventos; o banco é o do container `eventos-db`.

No `Caddyfile`, o bloco do eventos é:

```text
eventos.appdigital.tech {
    encode gzip
    reverse_proxy eventos:8000
}
```

## Variáveis importantes do `.env`

Além das descritas em `.env.example`:

| Variável | Valor em produção | Por quê |
|---|---|---|
| `DATABASE_URL` | aponta para `eventos-db` | banco PostgreSQL do container |
| `COOKIE_SECURE` | `1` | o site é só HTTPS |
| `TRUSTED_PROXY_COUNT` | `1` | o Caddy fica na frente; sem isto, os limites de tentativas de login e de consulta de protocolo valem para todos os usuários ao mesmo tempo |
| `APP_BASE_URL` | `https://eventos.appdigital.tech` | links nos e-mails |

## Atualizar o sistema depois de um push no `main`

O servidor **não** atualiza sozinho. Rode no VPS:

```bash
sudo -u deploy git -C /home/deploy/apps/eventos/EventosFMABC pull
cd /home/deploy/apps/eventos && docker compose up -d --build eventos
```

Use `sudo -u deploy` no Git: a pasta pertence ao usuário `deploy`, e rodando
como `root` o Git recusa o comando ("dubious ownership") sem atualizar nada.

O site fica fora do ar só alguns segundos enquanto o container é recriado.
Para ver se subiu bem:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}" | grep eventos
docker logs --tail 50 eventos
```

## Backup

O script `/usr/local/bin/eventos-backup` roda todo dia às 3h30
(`/etc/cron.d/eventos-backup`), exporta o banco do container `eventos-db` com
`pg_dump`, compacta e guarda os últimos 14 dias em `/root/backups-eventos/`.
Os anexos ficam dentro do banco, então entram no mesmo arquivo.

```bash
tail -3 /var/log/eventos-backup.log      # resultado dos últimos backups
/usr/local/bin/eventos-backup            # fazer um backup agora
```

Os backups ficam no próprio VPS. Copie-os periodicamente para fora do servidor.

### Restaurar um backup

Restaure só em um banco vazio (por exemplo, depois de recriar o volume), para
não misturar dados:

```bash
gunzip -c /root/backups-eventos/eventos-AAAA-MM-DD-HHMM.sql.gz \
  | docker exec -i eventos-db psql -U eventos -d eventos
```

## Rodar no computador (desenvolvimento)

Continua igual ao `README.md`: `python app.py` usa SQLite local quando
`DATABASE_URL` está vazia.
