from __future__ import annotations

import os
import subprocess


def mount_shared_disk(real_user: str, user_home: str, log) -> bool:
    log("Спроба монтування спільного диска UTM (9p)...")
    mount_point = f"{user_home}/MacFolder"

    for cmd in (
        f"umount -f {mount_point}",
        "umount -l share",
        "sed -i '/share \\/home/d' /etc/fstab",
        "systemctl daemon-reload",
    ):
        os.system(f"{cmd} > /dev/null 2>&1")

    os.makedirs(mount_point, exist_ok=True)
    mount_cmd = (
        f"mount -t 9p -o trans=virtio,version=9p2000.L,uid=1000,gid=1000,"
        f"dmode=0777,fmode=0777,allow_other,nofail share {mount_point}"
    )
    os.system(mount_cmd)

    if os.path.ismount(mount_point):
        os.system(f"chmod -R 777 {mount_point}")
        os.system(f"chown -R {real_user}:{real_user} {mount_point}")
        log("Спільний диск підключено.")
        return True

    log("Диск 'share' не знайдено — пропускаю (не критично).")
    return False
