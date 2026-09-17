#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for command in python makepkg sha256sum tar; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Missing build tool: $command" >&2
        echo "Install prerequisites on EndeavourOS:" >&2
        echo "  sudo pacman -S --needed base-devel python python-pip portaudio libsndfile libx11 libxext libxcb xcb-util-cursor xorg-xwayland" >&2
        exit 1
    fi
done

VERSION="$(python - <<'PY'
from vocari.__version__ import __version__
print(__version__)
PY
)"
BUILD_VENV="$ROOT/.venv-endeavouros-build"
WORK_DIR="$ROOT/build/endeavouros"
PYI_DIST="$WORK_DIR/pyinstaller-dist"
PACKAGE_DIR="$WORK_DIR/package"
ARCHIVE="Vocari-${VERSION}-linux-x86_64.tar.gz"

python -m venv "$BUILD_VENV"
"$BUILD_VENV/bin/python" -m pip install --upgrade pip
"$BUILD_VENV/bin/python" -m pip install -r requirements.txt -r requirements-dev.txt

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR" "$PACKAGE_DIR"
"$BUILD_VENV/bin/pyinstaller" vocari.spec --noconfirm --clean \
    --workpath "$WORK_DIR/pyinstaller-work" --distpath "$PYI_DIST"
cp -a assets "$PYI_DIST/Vocari/assets"

tar -C "$PYI_DIST" -czf "$PACKAGE_DIR/$ARCHIVE" Vocari
cp linux/vocari linux/vocari.desktop "$PACKAGE_DIR/"

archive_sha="$(sha256sum "$PACKAGE_DIR/$ARCHIVE" | cut -d' ' -f1)"
launcher_sha="$(sha256sum "$PACKAGE_DIR/vocari" | cut -d' ' -f1)"
desktop_sha="$(sha256sum "$PACKAGE_DIR/vocari.desktop" | cut -d' ' -f1)"
sed \
    -e "s/@VERSION@/$VERSION/g" \
    -e "s/@ARCHIVE_SHA256@/$archive_sha/g" \
    -e "s/@LAUNCHER_SHA256@/$launcher_sha/g" \
    -e "s/@DESKTOP_SHA256@/$desktop_sha/g" \
    linux/PKGBUILD.template > "$PACKAGE_DIR/PKGBUILD"

(
    cd "$PACKAGE_DIR"
    makepkg --force --noconfirm
)

mkdir -p "$ROOT/dist/linux"
cp "$PACKAGE_DIR"/vocari-bin-*.pkg.tar.zst "$ROOT/dist/linux/"
echo "Built:"
ls -lh "$ROOT/dist/linux"/vocari-bin-*.pkg.tar.zst
echo "Install with: sudo pacman -U dist/linux/vocari-bin-${VERSION}-1-x86_64.pkg.tar.zst"
