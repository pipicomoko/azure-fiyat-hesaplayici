# Postgres yedekleme

Günlük `pg_dump` (felaket kurtarma değil; temel kopya). Sorumlu kişi/rol: _[doldurulacak]_.

## Nasıl çalışır

Compose profili `backup` bir sidecar başlatır; dump'lar Docker volume `postgres_backups` içine yazılır, varsayılan **14 gün** tutulur (`BACKUP_KEEP_DAYS`).

```bash
docker compose --profile backup up -d
```

Yedek dizini (Mac Docker Desktop):

```bash
docker volume inspect azure-fiyat-hesaplayici_postgres_backups
```

Dosya adları genelde `apc-YYYY-MM-DD...sql.gz` biçimindedir.

## Geri yükleme (`pg_restore` / `psql`)

1. Uygulamayı durdurun (bağlantı kilidi olmasın):

```bash
docker compose stop app
```

2. Dump dosyasını kopyalayıp `psql` ile yükleyin (gzip ise önce açın):

```bash
docker compose cp pg-backup:/backups/SON_YEDEK.sql.gz ./son.sql.gz
gunzip -k son.sql.gz
docker compose exec -T postgres psql -U apc -d apc < son.sql
```

İmaj `pg_dump` düz SQL üretiyorsa `psql` yeter; custom format (`-Fc`) ise:

```bash
docker compose exec -T postgres pg_restore -U apc -d apc --clean --if-exists < son.dump
```

3. Uygulamayı tekrar başlatın: `docker compose start app`

Boş bir veritabanına yüklerken mevcut `apc` şemasını silmek veri kaybıdır; yalnızca bilinçli felaket senaryosunda `--clean` kullanın.
