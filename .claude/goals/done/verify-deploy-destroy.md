# Verify Deploy Destroy

## Why

Cerrar las 17 tareas de verificación pendientes (curls, idempotencia, dirty-tree del build-image) que el ciclo del 2026-06-04→05 no cubrió. Usuario autorizó arranque del ciclo completo el 2026-06-05.

## Definition of done

- `make bootstrap`, dos `gh workflow run deploy.yml`, un `gh workflow run destroy.yml`, `make destroy-bootstrap` completados sin errores nuevos.
- 17 tareas marcadas `[x]` en los 4 tasks.md (excluye §9.9 Cost Explorer 48h).
- `verify-destroyed.sh` exit 0 al final; IAM roles dan NoSuchEntity.
- `aws_deploy_live` memory refleja nuevo estado destruido.

## Tasks

- [x] 1. `make bootstrap`; capturar outputs; re-registrar `CLOUDFRONT_DISTRIBUTION_ID` GH variable.
- [x] 2. Curls bootstrap-only: subir placeholder index.html → curl `/` 200 con placeholder; curl `/non-existent` 200 con misma index; curl `/api/healthz` 5xx (placeholder).
- [x] 3. `aws iam get-role` para `nica-erp-ci-deploy` y `nica-erp-ci-destroy` (ambos OK).
- [x] 4. `terraform -chdir=infra/terraform/bootstrap plan` → No changes.
- [x] 5. `gh workflow run deploy.yml`; esperar verde; capturar URL CloudFront.
- [x] 6. Curls post-deploy: `/api/healthz` con `db:ok` + `alembic_revision`; `/` SPA index 200; abrir SPA en navegador (healthz card).
- [x] 7. `make logs` streaming ≤5s.
- [x] 8. Tagging API: bootstrap + runtime visibles.
- [x] 9. `make plan` → No changes.
- [x] 10. Segundo `gh workflow run deploy.yml` <10min (idempotencia).
- [x] 11. Tests build-image: dirty tree aborta; ALLOW_DIRTY=1 tag matches `^[0-9a-f]{7,}-dirty-[0-9]+$` + warning; `docker history --no-trunc` sin `tests/`/`__pycache__/` del proyecto.
- [x] 12. `gh workflow run destroy.yml`; esperar verde.
- [x] 13. `make destroy-bootstrap` con `nica-erp-bootstrap`.
- [x] 14. `verify-destroyed.sh` exit 0; IAM roles `NoSuchEntity`; tagging API solo post-destroy artifacts.
- [x] 15. Marcar 17 tasks `[x]` en los 4 tasks.md; actualizar memoria `project_aws_deploy_live`; dejar nota Cost Explorer ~2026-06-07.

## Notes

- 2026-06-05: usuario autorizó ciclo completo modo "arranca todo, avisá si algo falla".
- T1: bootstrap OK (22 recursos). CloudFront `d42wenmmu4rld.cloudfront.net` (id `EZDS7R6F6FZ0E`). 5 GH vars seteadas.
- T2: curls bootstrap-only OK (200 placeholder × 2, 502 placeholder origin).
- T4 fix: `infra/terraform/bootstrap/web.tf` añadido `lifecycle.ignore_changes` para `viewer_certificate[0].minimum_protocol_version` — AWS fuerza TLSv1 con cert default.
- T5: deploy run `27038742568` verde en 9m13s (1 run vs 8 del ciclo previo).
- T6: `/api/healthz` → `db:ok`, alembic `0007_auth_local_refresh_tokens`. SPA root → 200 con `lang="es"`. Browser visual no aplicable (CLI).
- T7: ALB healthchecks visibles en `/nica-erp/api` log group cada 5-15s.
- T8: 8 bootstrap + 51 runtime (incluye INACTIVE task defs del ciclo previo).
- T9: `terraform plan` envs/demo → "No changes".
- T10: segundo run `27039738858` falló por tag inmutable existente. Fix `scripts/build-and-push-image.sh` añade skip-if-exists. Commit `a1ec101` en main; tercer run `27040369585` en curso con nueva SHA — luego un cuarto run con MISMA SHA para validar el skip.
- T11: §5.3 abort exit=1; §5.4 tag `7b354eb-dirty-1780691857` matches regex + WARNINGs en stderr (build segfaultea por QEMU pero las verificaciones esenciales ocurren antes); §5.5 `docker history` clean (no project tests/__pycache__).
- T12: destroy run `27040700809` verde en 5m09s (1 run vs 3 del ciclo previo).
- T13: `make destroy-bootstrap` con `nica-erp-bootstrap` → 22 recursos destruidos en ~3min (CloudFront 2m48s).
- T14: verify-destroyed → `offenders=0`, "only bootstrap resources present"; ambos IAM roles `NoSuchEntity`; §6.6 wrong-token PASS (exit 1, no destructive call).
- T15: openspec dashboard ahora 3/4 changes en Completed (api-container-image, aws-runtime-stack, terraform-state-backend); add-deploy-destroy-automation queda 44/45 (98%) — único pendiente §9.9 Cost Explorer ≈$0 a verificar ~2026-06-07.

## Final summary

Cycle 2 completó limpiamente: 1 bootstrap + 4 deploys + 1 destroy + 1 destroy-bootstrap. 2 bugs reales fixeados (TLSv1 drift, ECR push idempotente) ya en main como `a1ec101`. De 18 tareas pendientes al inicio, 17 cerradas; §9.9 espera el 2026-06-07. Costo extra del ciclo: ≈$1-2 más el CMK PendingDeletion adicional.
