# Merge setelah review selesai

Repository menyediakan [`scripts/merge-after-review.sh`](../scripts/merge-after-review.sh) untuk menggabungkan `feature/production-reliability-upgrade` ke `main` setelah Pull Request disetujui.

Skrip ini aman secara default: tanpa `CONFIRM_MERGE=YES`, skrip hanya melakukan pemeriksaan dan tidak mengubah GitHub. Ia mensyaratkan working tree lokal bersih, dijalankan dari branch feature yang benar, menemukan tepat satu Pull Request terbuka ke `main`, memastikan head PR sama dengan `origin/feature/production-reliability-upgrade`, memastikan PR bukan draft, memerlukan `reviewDecision=APPROVED`, menunggu required checks lulus, dan memerlukan `mergeStateStatus=CLEAN`.

## Pemeriksaan tanpa merge

Jalankan dari checkout branch feature:

```bash
git switch feature/production-reliability-upgrade
git pull --ff-only
CHECK_ONLY=YES scripts/merge-after-review.sh
```

Jika review belum disetujui atau checks masih berjalan, skrip berhenti dengan status yang menjelaskan kondisi tersebut.

## Menunggu review dan checks

Untuk polling hingga satu jam, kemudian tetap berhenti tanpa merge:

```bash
WAIT_SECONDS=3600 POLL_SECONDS=60 CHECK_ONLY=YES scripts/merge-after-review.sh
```

## Merge setelah operator mengonfirmasi

Setelah GitHub menunjukkan review approved dan required checks pass, jalankan:

```bash
WAIT_SECONDS=3600 POLL_SECONDS=60 CONFIRM_MERGE=YES scripts/merge-after-review.sh
```

Strategi default adalah squash merge. Untuk merge commit atau rebase, gunakan `MERGE_METHOD=merge` atau `MERGE_METHOD=rebase`. Skrip tidak menghapus branch remote setelah merge, sehingga history dan rollback reference tetap tersedia.

```bash
MERGE_METHOD=merge CONFIRM_MERGE=YES scripts/merge-after-review.sh
```

## Catatan keamanan

Skrip tidak menerima token atau private key melalui argumen. GitHub CLI memakai sesi autentikasi lokalnya. Jangan menaruh token dalam `.env`, command history, atau file repository. Merge nyata adalah tindakan eksternal yang hanya dilakukan bila `CONFIRM_MERGE=YES` diberikan secara eksplisit.
