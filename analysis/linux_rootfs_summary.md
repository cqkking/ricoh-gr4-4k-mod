# Ricoh GR IV (v1.11) Linux RootFS (`INITFS`) & IPCU/Shmem Audit

## 1. Component Git Revisions (`/etc/revisions/*`)

| Component | Commit Hash / Revision |
| :--- | :--- |
| `bleapi-server` | `2732063 variant/2025-07-HDF-OW-model-development bleapi-server` |
| `camera-controller` | `9d0600e variant/2025-07-HDF-OW-model-development camera-controller` |
| `camera-ipcu-spec` | `f845193 variant/2025-07-HDF-OW-model-development camera-ipcu-spec` |
| `externals` | `81b148d variant/2025-07-HDF-OW-model-development externals` |
| `kernel` | `7cacff0c4 variant/2025-07-HDF-OW-model-development kernel` |
| `meta-ricoh-dpf` | `08c8a5b variant/2025-07-HDF-OW-model-development meta-ricoh-dpf` |
| `meta-ricoh-eg1` | `85622fd variant/2025-07-HDF-OW-model-development meta-ricoh-eg1` |
| `mtp-server` | `6edb067 variant/2025-07-HDF-OW-model-development mtp-server` |
| `network-manager` | `04c8062 variant/2025-07-HDF-OW-model-development network-manager` |
| `sdk` | `e32a5d74 variant/2025-07-HDF-OW-model-development sdk` |
| `shmem-manager` | `a19a067 variant/2025-07-HDF-OW-model-development shmem-manager` |
| `system-manager` | `74f77ea variant/2025-07-HDF-OW-model-development system-manager` |
| `webapi-server` | `c51c8b2 variant/2025-07-HDF-OW-model-development webapi-server` |

## 2. Key Linux Binaries & Shared Libraries

| Binary Path | Size (Bytes) | Exported Symbols | Imported Symbols | Key Dependencies (`DT_NEEDED`) |
| :--- | ---: | ---: | ---: | :--- |
| `usr/lib/libshmem_manager.so` | 9,448 | 21 | 22 | `libc.so.6`, `ld-linux.so.3` |
| `usr/lib/libcmfwk.so` | 21,896 | 16 | 47 | `libpthread.so.0`, `libc.so.6` |
| `usr/lib/libcamera-controller.so` | 863,184 | 2125 | 245 | `libshmem_manager.so`, `libprotobuf.so.30`, `libgrpc++_unsecure.so.1.46`, `libcmfwk.so`, `libstdc++.so.6` (+3) |
| `usr/bin/camctld` | 637,988 | 1627 | 265 | `libshmem_manager.so`, `libtbb.so.12`, `libprotobuf.so.30`, `libgrpc++_unsecure.so.1.46`, `libcmfwk.so` (+4) |
| `usr/bin/sysmgrd` | 145,320 | 266 | 195 | `libcamera-controller.so`, `libBtStack.so`, `libstdc++.so.6`, `libgcc_s.so.1`, `libc.so.6` (+1) |
| `usr/bin/webapid` | 829,844 | 1142 | 431 | `libcamera-controller.so`, `libstdc++.so.6`, `libgcc_s.so.1`, `libc.so.6`, `ld-linux.so.3` |
| `usr/bin/membinrdwr` | 13,812 | 0 | 23 | `libcmfwk.so`, `libc.so.6` |
| `usr/bin/membinrdwriq` | 13,812 | 0 | 22 | `libcmfwk.so`, `libc.so.6` |
| `usr/bin/membinrdwrawb` | 13,808 | 0 | 21 | `libcmfwk.so`, `libc.so.6` |

## 3. Notable IPCU, Shmem & IQ Symbols

### `usr/lib/libshmem_manager.so`

- `os_create_memory` @ `0x1095` (4 B)
- `os_unmap_physical_memory` @ `0x10f1` (4 B)
- `os_create_mutex` @ `0x10f5` (252 B)
- `shmem_free` @ `0xf4d` (60 B)
- `shmem_alloc` @ `0xec5` (136 B)
- `shmem_init` @ `0xdb1` (276 B)
- `shmem_dump_block` @ `0xfc9` (56 B)
- `shmem_use_count` @ `0x1069` (44 B)
- `os_mutex_lock` @ `0x1265` (20 B)
- `os_mem_free` @ `0x1291` (4 B)
- `shmem_phys_to_virt` @ `0xfa9` (32 B)
- `os_mem_alloc` @ `0x128d` (4 B)
- `shmem_init_config` @ `0xbed` (364 B)
- `os_map_physical_memory` @ `0x1099` (88 B)
- `shmem_virt_to_phys` @ `0xf89` (32 B)
- `os_mutex_unlock` @ `0x1279` (20 B)
- `shmem_dump_mng_block` @ `0x1001` (104 B)
- `shmem_get_mng_size` @ `0xbcd` (32 B)
- `os_open_mutex` @ `0x11f1` (116 B)
- `os_log` @ `0x1295` (104 B)
- `shmem_exit` @ `0xd59` (88 B)

### `usr/lib/libcmfwk.so`

- `FJ_MM_phys_to_virt` @ `0x339c` (4 B)
- `FJ_MM_virt_to_phys` @ `0x3398` (4 B)
- `fj_mm_munmap` @ `0x2bb4` (24 B)
- `fj_mm_mmap` @ `0x2af8` (188 B)
- `fj_mm_close` @ `0x2e8c` (612 B)
- `FJ_IPCU_Close` @ `0x1cf4` (864 B)
- `FJ_IPCU_Send` @ `0x23f4` (876 B)
- `fj_mm_get_shared_val` @ `0x29b4` (260 B)
- `fj_mm_is_shared_region` @ `0x30f8` (88 B)
- `FJ_MM_getPhysAddrInfo` @ `0x335c` (60 B)
- `fj_mm_open` @ `0x2bcc` (704 B)
- `FJ_IPCU_Open` @ `0x2054` (928 B)
- `fj_mm_virt_to_phys` @ `0x30f0` (8 B)
- `fj_mm_make_mmap_cfg` @ `0x2ab8` (64 B)
- `FJ_IPCU_SetReceiverCB` @ `0x2760` (596 B)
- `fj_mm_phys_to_virt` @ `0x3150` (524 B)

### `usr/bin/membinrdwriq`

