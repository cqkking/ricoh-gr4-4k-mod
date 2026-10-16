#!/usr/bin/env python3
"""Ricoh GR IV (v1.11 fwdc248b.bin) Firmware Container Unpacker, Validator & Rebuilder.

Supports:
  - Container LZSS decoding & dual word-sum checksum verification
  - Splitting all 13 top-level payload sections (BOOTPARA .. RES)
  - Unpacking all 31 embedded RES files (including China Mainland LE_CN_S.bin / RT_CN_S.bin)
  - Extracting INITFS SquashFS 4.0 (LZ4 block compressed) Linux root filesystem
  - Rebuilding valid, flashable fwdc248b.bin images from byte-patch manifests or modified payloads

Usage:
  python tools/fw_container.py info     [firmware/official/v1.11/fwdc248b.bin]
  python tools/fw_container.py unpack   [firmware/official/v1.11/fwdc248b.bin] [-o firmware/unpacked/v1.11]
  python tools/fw_container.py patch    <patch_spec.json> [-i firmware/official/v1.11/fwdc248b.bin] [-o output/fwdc248b.bin]
"""
import argparse
import hashlib
import json
import os
import struct
import sys
from pathlib import Path

OFFICIAL_V111_SHA256 = "a2f664dfca034059eb0fd6e18ab08684c326b4a034d85c164dad7e1ec9b5655f"
OFFICIAL_V111_BYTES = 38648776
DECODED_PAYLOAD_BYTES = 67948280
RTOS_VADDR_BASE = 0x53000000

HEADER_SIZE = 128
MAGIC = b"RICOH\0\0\0"
FOOTER_MAGIC = b"\xa5\x5a\x5a\xa5"
MAX_DISTANCE = 0x2000
LITERAL_CHUNK = 0x6000


class FirmwareError(Exception):
    pass


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def word_sum(data: bytes) -> int:
    if len(data) % 4 != 0:
        raise FirmwareError(f"Data length {len(data)} is not 4-byte aligned")
    return sum(w for (w,) in struct.iter_unpack("<I", data)) & 0xFFFFFFFF


def decode_container(data: bytes, limit: int = 256 * 1024 * 1024):
    """Decode Ricoh LZSS-framed firmware container into raw payload bytes."""
    if len(data) < 160 or data[:8] != MAGIC:
        raise FirmwareError("Not a valid RICOH firmware container (missing magic)")
    out = bytearray()
    frames = []
    cursor = HEADER_SIZE
    while True:
        start = cursor
        if cursor + 2 > len(data):
            raise FirmwareError("Container missing frame terminator")
        descriptor = int.from_bytes(data[cursor : cursor + 2], "big")
        cursor += 2
        if descriptor == 0:
            return bytes(out), frames, cursor
        size = descriptor & 0x7FFF
        end = cursor + size
        if not size or end > len(data):
            raise FirmwareError(f"Container invalid frame at {start:#x}")
        output_start = len(out)
        if descriptor & 0x8000:
            out += data[cursor:end]
            cursor = end
        else:
            while cursor < end:
                if cursor + 2 > end:
                    raise FirmwareError(f"Container truncated flags at {cursor:#x}")
                flags = int.from_bytes(data[cursor : cursor + 2], "big")
                cursor += 2
                for bit in range(15, -1, -1):
                    if cursor == end:
                        break
                    if not (flags & (1 << bit)):
                        out.append(data[cursor])
                        cursor += 1
                        continue
                    if cursor + 2 > end:
                        raise FirmwareError("Container truncated back-reference")
                    a, b = data[cursor], data[cursor + 1]
                    cursor += 2
                    distance = ((a >> 3) << 8) | b
                    length = a & 7
                    if length == 7:
                        while True:
                            if cursor >= end:
                                raise FirmwareError("Container truncated length extension")
                            extension = data[cursor]
                            cursor += 1
                            length += extension
                            if extension != 255:
                                break
                    if distance == 0:
                        break
                    if distance > len(out):
                        raise FirmwareError("Container reference before start of output")
                    count = length + 3
                    if distance >= count:
                        out += out[-distance : len(out) - distance + count]
                    else:
                        pattern = bytes(out[-distance:])
                        out += (pattern * ((count + distance - 1) // distance))[:count]
                if len(out) > limit:
                    raise FirmwareError("Decoded payload size limit exceeded")
        frames.append((start, end, output_start, len(out)))


def verify_container(data: bytes, payload: bytes = None, consumed: int = None) -> bytes:
    """Verify container footer magic, size fields, and both 32-bit word-sum checksums."""
    if payload is None:
        payload, _, consumed = decode_container(data)
    if data[-20:-16] != FOOTER_MAGIC:
        raise FirmwareError("Container footer magic (0xA55A5AA5) missing")
    enc_size, dec_size = struct.unpack_from("<II", data, len(data) - 12)
    if enc_size != consumed - HEADER_SIZE or dec_size != len(payload):
        raise FirmwareError(
            f"Size mismatch: header says enc={enc_size}, dec={dec_size}; actual enc={consumed - HEADER_SIZE}, dec={len(payload)}"
        )
    if word_sum(data) != 0:
        raise FirmwareError(f"Outer container checksum mismatch (word_sum={word_sum(data):#010x})")
    if word_sum(payload) != 0:
        raise FirmwareError(f"Inner payload checksum mismatch (word_sum={word_sum(payload):#010x})")
    return payload


def parse_sections(payload: bytes):
    """Parse all top-level sections in the decoded payload, including the RES multi-file archive."""
    out = []
    pos = 0
    while pos + 16 <= len(payload):
        tag_raw = payload[pos : pos + 8].rstrip(b"\0")
        if not tag_raw or not tag_raw.isalnum() or not tag_raw.isupper():
            break
        tag = tag_raw.decode("ascii")
        flags, size_or_count = struct.unpack_from("<II", payload, pos + 8)
        if tag == "RES":
            # For RES, size_or_count is the file count (31 files), ending at len(payload) - 4 (checksum word)
            res_entries = parse_res_entries(payload, pos + 16, size_or_count)
            res_end = res_entries[-1]["data_end"] if res_entries else pos + 16
            out.append({
                "name": tag,
                "header_offset": pos,
                "data_start": pos + 16,
                "data_end": res_end,
                "size": res_end - (pos + 16),
                "flags": flags,
                "file_count": size_or_count,
                "res_entries": res_entries,
            })
            break
        if pos + 16 + size_or_count > len(payload):
            break
        out.append({
            "name": tag,
            "header_offset": pos,
            "data_start": pos + 16,
            "data_end": pos + 16 + size_or_count,
            "size": size_or_count,
            "flags": flags,
        })
        pos += 16 + size_or_count
    return out


def parse_res_entries(payload: bytes, start_pos: int, count: int):
    """Parse the embedded A:\\Resource\\... and A:\\sound\\... files inside the RES section."""
    entries = []
    pos = start_pos
    for idx in range(count):
        if pos + 36 > len(payload) - 4:
            raise FirmwareError(f"Truncated RES entry {idx} at {pos:#x}")
        path_raw = payload[pos : pos + 32].rstrip(b"\0")
        path_str = path_raw.decode("ascii", errors="replace")
        file_size = struct.unpack_from("<I", payload, pos + 32)[0]
        data_start = pos + 36
        data_end = data_start + file_size
        entries.append({
            "index": idx,
            "header_offset": pos,
            "dos_path": path_str,
            "rel_path": path_str.replace("A:\\", "").replace("\\", "/"),
            "data_start": data_start,
            "data_end": data_end,
            "size": file_size,
        })
        pos = data_end
    return entries


def extract_squashfs(sq_bytes: bytes, dest_dir: Path):
    """Extract LZ4-block compressed SquashFS 4.0 image from INITFS section."""
    import lz4.block
    from PySquashfsImage import SquashFsImage
    from PySquashfsImage.compressor import LZ4Compressor

    # Patch PySquashfsImage to use raw LZ4 block decompression as required by SquashFS 4.0
    LZ4Compressor.uncompress = lambda self, src, size, outsize: lz4.block.decompress(
        src, uncompressed_size=outsize
    )

    bytes_used = struct.unpack_from("<Q", sq_bytes, 40)[0]
    img = SquashFsImage.from_bytes(sq_bytes[:bytes_used])
    extracted_files = 0
    symlinks = []

    dest_dir.mkdir(parents=True, exist_ok=True)
    for item in img:
        rel = item.path.lstrip("/")
        if not rel:
            continue
        target = dest_dir / rel
        if item.is_dir:
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_symlink:
            symlinks.append({
                "path": item.path,
                "link_target": item.readlink() if hasattr(item, "readlink") else "",
            })
        elif item.is_file:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(item.read_bytes())
            extracted_files += 1
    img.close()

    if symlinks:
        (dest_dir / "_symlinks.json").write_text(
            json.dumps(symlinks, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return extracted_files, len(symlinks)


def rezero_payload(payload: bytes) -> bytes:
    buf = bytearray(payload)
    last = struct.unpack_from("<I", buf, len(buf) - 4)[0]
    struct.pack_into("<I", buf, len(buf) - 4, (last - word_sum(buf)) & 0xFFFFFFFF)
    return bytes(buf)


def literal_frames(data: bytes) -> bytes:
    out = bytearray()
    for pos in range(0, len(data), LITERAL_CHUNK):
        chunk = data[pos : pos + LITERAL_CHUNK]
        out += struct.pack(">H", 0x8000 | len(chunk)) + chunk
    return bytes(out)


def diff_offsets(a: bytes, b: bytes, block: int = 1 << 16):
    if len(a) != len(b):
        raise FirmwareError("Payload length mismatch")
    out = []
    for pos in range(0, len(a), block):
        x, y = a[pos : pos + block], b[pos : pos + block]
        if x != y:
            out += [pos + i for i in range(len(x)) if x[i] != y[i]]
    return out


def rebuild_container(source: bytes, frames, consumed: int, patched_payload: bytes, changed_offsets):
    body = bytearray()
    reemitted = 0
    for c0, c1, d0, d1 in frames:
        if any(d0 <= c < d1 or c < d0 < c + MAX_DISTANCE for c in changed_offsets):
            body += literal_frames(patched_payload[d0:d1])
            reemitted += 1
        else:
            body += source[c0:c1]
    body += b"\0\0"
    trailer = bytearray(source[consumed:])
    struct.pack_into("<II", trailer, len(trailer) - 12, len(body), len(patched_payload))
    struct.pack_into("<I", trailer, len(trailer) - 4, 0)
    padding = bytes((-HEADER_SIZE - len(body) - len(trailer)) % 4)
    out = bytearray(source[:HEADER_SIZE] + body + padding + trailer)
    struct.pack_into("<I", out, len(out) - 4, (-word_sum(out)) & 0xFFFFFFFF)
    return bytes(out), reemitted


def cmd_info(args):
    data = args.input.read_bytes()
    digest = sha256_hex(data)
    print(f"File       : {args.input}")
    print(f"Size       : {len(data):,} bytes ({len(data):#x})")
    print(f"SHA-256    : {digest}")
    print(f"Official   : {'YES (RICOH GR IV v1.11)' if digest == OFFICIAL_V111_SHA256 else 'MODIFIED / CUSTOM'}")

    model = data[8:20].rstrip(b"\0").decode("ascii", errors="replace")
    vendor = data[20:48].rstrip(b"\0").decode("ascii", errors="replace")
    build_ts = data[84:108].rstrip(b"\0").decode("ascii", errors="replace")
    print(f"Model      : {model} ({vendor})")
    print(f"Build Time : {build_ts}")

    payload, frames, consumed = decode_container(data)
    verify_container(data, payload, consumed)
    print(f"Container  : VALID (frames={len(frames)}, decoded={len(payload):,} bytes)")
    print("\nPayload Sections:")
    for idx, sec in enumerate(parse_sections(payload)):
        extra = ""
        if sec["name"] == "RTOS":
            extra = f"  [vaddr {RTOS_VADDR_BASE:#010x}..{RTOS_VADDR_BASE + sec['size']:#010x}]"
        elif sec["name"] == "RES":
            extra = f"  [{sec['file_count']} embedded resource files]"
        print(
            f"  [{idx:02d}] {sec['name']:10s} start={sec['data_start']:#010x} end={sec['data_end']:#010x} "
            f"size={sec['size']:11,d} B  flags={sec['flags']:#010x}{extra}"
        )
    return 0


def cmd_unpack(args):
    data = args.input.read_bytes()
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Decoding {args.input} ...")
    payload, frames, consumed = decode_container(data)
    verify_container(data, payload, consumed)

    payload_path = out_dir / "payload.bin"
    payload_path.write_bytes(payload)
    print(f"Wrote decoded payload: {payload_path} ({len(payload):,} bytes)")

    sec_dir = out_dir / "sections"
    sec_dir.mkdir(parents=True, exist_ok=True)
    secs = parse_sections(payload)
    manifest = {
        "source_file": str(args.input),
        "source_sha256": sha256_hex(data),
        "source_bytes": len(data),
        "payload_sha256": sha256_hex(payload),
        "payload_bytes": len(payload),
        "rtos_vaddr_base": hex(RTOS_VADDR_BASE),
        "sections": [],
    }

    for idx, sec in enumerate(secs):
        sec_file = sec_dir / f"{idx:02d}_{sec['name']}.bin"
        sec_bytes = payload[sec["data_start"] : sec["data_end"]]
        sec_file.write_bytes(sec_bytes)
        sec_info = {
            "index": idx,
            "name": sec["name"],
            "header_offset": hex(sec["header_offset"]),
            "data_start": hex(sec["data_start"]),
            "data_end": hex(sec["data_end"]),
            "size": sec["size"],
            "flags": hex(sec["flags"]),
            "sha256": sha256_hex(sec_bytes),
        }
        if sec["name"] == "RES":
            res_out = out_dir / "res"
            res_out.mkdir(parents=True, exist_ok=True)
            for entry in sec["res_entries"]:
                dest = res_out / entry["rel_path"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(payload[entry["data_start"] : entry["data_end"]])
            sec_info["res_entries"] = [
                {
                    "index": e["index"],
                    "dos_path": e["dos_path"],
                    "rel_path": e["rel_path"],
                    "data_start": hex(e["data_start"]),
                    "data_end": hex(e["data_end"]),
                    "size": e["size"],
                }
                for e in sec["res_entries"]
            ]
            print(f"  Unpacked {len(sec['res_entries'])} RES files -> {res_out}")
        elif sec["name"] == "INITFS" and not args.skip_squashfs:
            sq_out = out_dir / "initfs_root"
            n_files, n_links = extract_squashfs(sec_bytes, sq_out)
            sec_info["squashfs_files"] = n_files
            sec_info["squashfs_symlinks"] = n_links
            print(f"  Extracted INITFS SquashFS ({n_files} files, {n_links} symlinks) -> {sq_out}")
        manifest["sections"].append(sec_info)

    manifest_path = out_dir / "unpack_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Unpack complete. Manifest saved to {manifest_path}")
    return 0


def cmd_patch(args):
    source = args.input.read_bytes()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    print(f"Applying patch spec: {spec.get('name', args.spec.name)}")

    payload, frames, consumed = decode_container(source)
    verify_container(source, payload, consumed)
    buf = bytearray(payload)

    for item in spec.get("changes", []):
        off = int(str(item["offset"]), 0)
        old_bytes = bytes.fromhex(item["expected_hex"])
        new_bytes = bytes.fromhex(item["replacement_hex"])
        desc = item.get("description", "")
        if len(old_bytes) != len(new_bytes):
            raise FirmwareError(f"Patch length mismatch at {off:#x}")
        actual = bytes(buf[off : off + len(old_bytes)])
        if actual != old_bytes:
            raise FirmwareError(
                f"Unexpected original bytes at {off:#x}: got {actual.hex()}, expected {old_bytes.hex()}"
            )
        buf[off : off + len(new_bytes)] = new_bytes
        print(f"  Patched {off:#010x}: {old_bytes.hex()} -> {new_bytes.hex()} ({desc})")

    patched = rezero_payload(bytes(buf))
    changed = diff_offsets(payload, patched)
    out_bytes, reemitted = rebuild_container(source, frames, consumed, patched, changed)

    # Round-trip verification
    again, _, used = decode_container(out_bytes)
    if again != patched:
        raise FirmwareError("Verification failed: decoded output does not match patched payload")
    verify_container(out_bytes, again, used)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(out_bytes)
    print(
        f"Verified & wrote {args.output} ({len(out_bytes):,} bytes, {reemitted} frames re-emitted, SHA-256={sha256_hex(out_bytes)})"
    )
    return 0


def main(argv=None):
    repo_root = Path(__file__).resolve().parent.parent
    default_fw = repo_root / "firmware" / "official" / "v1.11" / "fwdc248b.bin"
    default_unpacked = repo_root / "firmware" / "unpacked" / "v1.11"

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_info = sub.add_parser("info", help="Verify and print firmware container & section layout")
    p_info.add_argument("input", nargs="?", type=Path, default=default_fw)

    p_unpack = sub.add_parser("unpack", help="Unpack firmware container, sections, RES, and INITFS SquashFS")
    p_unpack.add_argument("input", nargs="?", type=Path, default=default_fw)
    p_unpack.add_argument("-o", "--output-dir", type=Path, default=default_unpacked)
    p_unpack.add_argument("--skip-squashfs", action="store_true", help="Skip extracting INITFS SquashFS")

    p_patch = sub.add_parser("patch", help="Apply a JSON byte-patch spec and rebuild verified fwdc248b.bin")
    p_patch.add_argument("spec", type=Path, help="Path to JSON patch specification")
    p_patch.add_argument("-i", "--input", type=Path, default=default_fw)
    p_patch.add_argument("-o", "--output", type=Path, default=repo_root / "output" / "fwdc248b.bin")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "info":
            return cmd_info(args)
        elif args.cmd == "unpack":
            return cmd_unpack(args)
        elif args.cmd == "patch":
            return cmd_patch(args)
    except FirmwareError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
