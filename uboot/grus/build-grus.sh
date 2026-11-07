#!/bin/bash
# grus-build.sh: build grus U-Boot and pack the ABL boot image.
# (grus-specific copy of sirius-build.sh: grus.config fragment and the
#  qcom/sdm710-xiaomi-grus device tree; everything else identical.)
#
# Env overrides: OUT, IMG, ENV_FILE, CROSS_COMPILE, JOBS, DEVICE_TREE.
set -e
UBOOT="$(cd "$(dirname "$0")" && pwd)"
OUT=${OUT:-$UBOOT/workspace/build/uboot-grus}
IMG=${IMG:-$UBOOT/build/boot-grus.img}
case "$(uname -m)" in
  aarch64|arm64) DEF_CROSS= ;;
  *)             DEF_CROSS=aarch64-linux-gnu- ;;
esac
CROSS=${CROSS_COMPILE-$DEF_CROSS}
JOBS=${JOBS:-$(nproc)}
DT=${DEVICE_TREE:-qcom/sdm710-xiaomi-grus}
mkdir -p "$OUT" "$(dirname "$IMG")"
# Diagnostic framebuffer probes are opt-in now: build with GRUS_DIAG=1.
if [ "${GRUS_DIAG:-0}" = "1" ]; then
  if [ -f "$UBOOT/board/xiaomi/grus/diag.patch" ]; then
    echo "=== apply diag.patch (framebuffer proof-of-life bands) ==="
    git -C "$UBOOT" apply -v board/xiaomi/grus/diag.patch
  fi
  if [ -f "$UBOOT/board/xiaomi/grus/inject-main.py" ]; then
    echo "=== inject main_loop framebuffer progress markers ==="
    python3 "$UBOOT/board/xiaomi/grus/inject-main.py" "$UBOOT/common/main.c"
  fi
  if [ -f "$UBOOT/board/xiaomi/grus/inject-device.py" ]; then
    echo "=== inject per-device probe counter (device.c) ==="
    python3 "$UBOOT/board/xiaomi/grus/inject-device.py" "$UBOOT/drivers/core/device.c"
  fi
fi
# grus has no reachable console: autoboot would block on a dead stdin before
# bootcmd runs. Always run bootcmd unconditionally at the top of main_loop().
if [ -f "$UBOOT/board/xiaomi/grus/inject-forceboot.py" ]; then
  echo "=== inject unconditional bootcmd run in main_loop ==="
  python3 "$UBOOT/board/xiaomi/grus/inject-forceboot.py" "$UBOOT/common/main.c"
fi
make -C "$UBOOT" CROSS_COMPILE="$CROSS" O="$OUT" qcom_defconfig qcom-phone.config grus.config
echo "=== build $DT ==="
ENV_ARGS=()
if [ -n "${ENV_FILE:-}" ]; then
  ENV_ARGS=("CONFIG_ENV_DEFAULT_ENV_TEXT_FILE=$ENV_FILE")
fi
make -C "$UBOOT" CROSS_COMPILE="$CROSS" O="$OUT" -j"$JOBS" DEVICE_TREE="$DT" "${ENV_ARGS[@]}"
echo "=== payload + boot image ==="
gzip -c "$OUT/u-boot-nodtb.bin" > "$OUT/u-boot-nodtb.bin.gz"
DTB="$OUT/dts/upstream/src/arm64/qcom/sdm710-xiaomi-grus.dtb"
test -f "$DTB" || { echo "missing dtb $DTB"; exit 1; }
cat "$OUT/u-boot-nodtb.bin.gz" "$DTB" > "$OUT/uboot-payload"
command -v mkbootimg >/dev/null || { echo "missing mkbootimg"; exit 1; }
mkbootimg --kernel_offset 0x00008000 --pagesize 4096 --kernel "$OUT/uboot-payload" -o "$IMG"
ls -lh "$IMG"
echo UBOOT-GRUS-DONE
