# GitOps iskeleti (Faz 5)

Ürün (Samba → yetki → onay → Excel) stabilize olduktan sonra:

1. CI yeşil kalsın (`.github/workflows/ci.yml`)
2. İmaj push: `.github/workflows/build-push.yml` → GHCR
3. Manifest: `k8s/app-deployment.yaml` (OWNER/secret yer tutucularını doldur)
4. Argo CD: `k8s/argocd-application.yaml`

**Not:** Samba ve Postgres stateful; K8s’te PVC veya yönetilen DB ayrı karar.
Şimdilik yerel `docker compose` geliştirme ortamıdır.
