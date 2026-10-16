#!/usr/bin/env python3
"""Ricoh GR IV (v1.11) Linux RootFS (INITFS SquashFS) ELF & IPCU/Shmem Analyzer.

Analyzes key Linux daemons and shared libraries extracted from INITFS:
  - /usr/bin/camctld (Camera Controller Daemon)
  - /usr/lib/libcamera-controller.so (High-level Camera Controller C++ Library)
  - /usr/lib/libcmfwk.so (Socionext/Ricoh IPCU & Mmap Framework)
  - /usr/lib/libshmem_manager.so (Shared Memory Manager between Linux & T-Kernel RTOS)
  - /usr/bin/membinrdwr, membinrdwriq, membinrdwrawb (IQ / AWB / Shmem diagnostic tools)
  - /etc/revisions/* (Component git commit hashes)
"""
import json
import re
import sys
from pathlib import Path
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection


def extract_elf_info(elf_path: Path):
    info = {
        "file": elf_path.name,
        "size": elf_path.stat().st_size,
        "needed_libs": [],
        "exported_symbols": [],
        "imported_symbols": [],
        "interesting_strings": [],
    }
    raw = elf_path.read_bytes()
    with elf_path.open("rb") as f:
        elf = ELFFile(f)
        dynamic = elf.get_section_by_name(".dynamic")
        if dynamic:
            for tag in dynamic.iter_tags():
                if tag.entry.d_tag == "DT_NEEDED":
                    info["needed_libs"].append(tag.needed)

        for section in elf.iter_sections():
            if isinstance(section, SymbolTableSection):
                for sym in section.iter_symbols():
                    name = sym.name
                    if not name:
                        continue
                    bind = sym["st_info"]["bind"]
                    shndx = sym["st_shndx"]
                    val = sym["st_value"]
                    if shndx == "SHN_UNDEF":
                        if name not in info["imported_symbols"]:
                            info["imported_symbols"].append(name)
                    elif bind in ("STB_GLOBAL", "STB_WEAK") and val != 0:
                        info["exported_symbols"].append({"name": name, "vaddr": hex(val), "size": sym["st_size"]})

    keywords = [
        b"movie", b"video", b"4k", b"2160", b"1080", b"h264", b"h265", b"hevc",
        b"hlg", b"tone", b"color", b"matrix", b"lut", b"ipcu", b"shmem", b"dng",
        b"raw", b"jpg", b"jpeg", b"iq", b"region", b"dest", b"chn", b"lang",
    ]
    seen = set()
    for m in re.finditer(rb"[ -~]{4,100}", raw):
        s = m.group(0)
        sl = s.lower()
        if any(k in sl for k in keywords):
            txt = s.decode("ascii", errors="replace")
            if txt not in seen:
                seen.add(txt)
                info["interesting_strings"].append({"offset": hex(m.start()), "text": txt})
    return info


def main():
    repo_root = Path(__file__).resolve().parent.parent
    initfs_root = repo_root / "firmware" / "unpacked" / "v1.11" / "initfs_root"
    analysis_dir = repo_root / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    if not initfs_root.exists():
        print(f"ERROR: {initfs_root} not found. Run 'python tools/fw_container.py unpack' first.", file=sys.stderr)
        return 1

    # 1. Read /etc/revisions/*
    rev_dir = initfs_root / "etc" / "revisions"
    revisions = {}
    if rev_dir.exists():
        for p in sorted(rev_dir.iterdir()):
            if p.is_file():
                revisions[p.name] = p.read_text(encoding="utf-8", errors="replace").strip()

    # 2. Analyze target ELFs
    targets = [
        initfs_root / "usr" / "lib" / "libshmem_manager.so",
        initfs_root / "usr" / "lib" / "libcmfwk.so",
        initfs_root / "usr" / "lib" / "libcamera-controller.so",
        initfs_root / "usr" / "bin" / "camctld",
        initfs_root / "usr" / "bin" / "sysmgrd",
        initfs_root / "usr" / "bin" / "webapid",
        initfs_root / "usr" / "bin" / "membinrdwr",
        initfs_root / "usr" / "bin" / "membinrdwriq",
        initfs_root / "usr" / "bin" / "membinrdwrawb",
    ]

    elf_reports = {}
    for t in targets:
        if t.exists():
            print(f"Analyzing {t.relative_to(initfs_root)} ...")
            elf_reports[str(t.relative_to(initfs_root)).replace("\\", "/")] = extract_elf_info(t)

    out_json = analysis_dir / "linux_rootfs_audit.json"
    out_json.write_text(
        json.dumps({"revisions": revisions, "binaries": elf_reports}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 3. Generate concise Markdown summary
    md = [
        "# Ricoh GR IV (v1.11) Linux RootFS (`INITFS`) & IPCU/Shmem Audit\n",
        "## 1. Component Git Revisions (`/etc/revisions/*`)\n",
        "| Component | Commit Hash / Revision |",
        "| :--- | :--- |",
    ]
    for k, v in revisions.items():
        md.append(f"| `{k}` | `{v}` |")
    md.append("\n## 2. Key Linux Binaries & Shared Libraries\n")
    md.append("| Binary Path | Size (Bytes) | Exported Symbols | Imported Symbols | Key Dependencies (`DT_NEEDED`) |")
    md.append("| :--- | ---: | ---: | ---: | :--- |")
    for rel_path, rep in elf_reports.items():
        deps = ", ".join(f"`{d}`" for d in rep["needed_libs"][:5])
        if len(rep["needed_libs"]) > 5:
            deps += f" (+{len(rep['needed_libs']) - 5})"
        md.append(
            f"| `{rel_path}` | {rep['size']:,} | {len(rep['exported_symbols'])} | {len(rep['imported_symbols'])} | {deps} |"
        )

    md.append("\n## 3. Notable IPCU, Shmem & IQ Symbols\n")
    for rel_path in ("usr/lib/libshmem_manager.so", "usr/lib/libcmfwk.so", "usr/bin/membinrdwriq"):
        rep = elf_reports.get(rel_path)
        if not rep:
            continue
        md.append(f"### `{rel_path}`\n")
        for sym in rep["exported_symbols"][:25]:
            md.append(f"- `{sym['name']}` @ `{sym['vaddr']}` ({sym['size']} B)")
        md.append("")

    out_md = analysis_dir / "linux_rootfs_summary.md"
    out_md.write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {out_json} and {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
