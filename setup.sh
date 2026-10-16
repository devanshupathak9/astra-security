#!/usr/bin/env bash
# One-time setup: Python deps, Java + jadx (local, no sudo), sample APK, .env.
# Works on macOS and Linux. Usage: ./setup.sh
set -euo pipefail

JADX_VERSION="1.5.6"
JAVA_VERSION="17"
APK_URL="https://github.com/hax0rgb/InsecureShop/releases/download/v1.0/InsecureShop.apk"

cd "$(dirname "$0")"
ROOT="$(pwd)"
TOOLS="$ROOT/tools"
mkdir -p "$TOOLS/bin" apks

# ---------- 1. Python ----------
echo "==> Python"
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"'
if [ -z "${VIRTUAL_ENV:-}" ]; then
  [ -d .venv ] || python3 -m venv .venv
  source .venv/bin/activate
  echo "    using .venv (run: source .venv/bin/activate)"
else
  echo "    using active venv: $VIRTUAL_ENV"
fi
pip install -q -r requirements.txt

# ---------- 2. Java (needed by jadx) ----------
echo "==> Java"
java_ok() { "$1" -version 2>&1 | grep -qE 'version "(1[1-9]|[2-9][0-9])'; }
if command -v java >/dev/null && java_ok java; then
  echo "    system Java is fine"
elif [ -x "$TOOLS/jdk/bin/java" ] || [ -x "$TOOLS/jdk/Contents/Home/bin/java" ]; then
  echo "    local Java already installed"
else
  case "$(uname -s)" in Darwin) OS=mac ;; Linux) OS=linux ;; *) echo "unsupported OS"; exit 1 ;; esac
  case "$(uname -m)" in arm64|aarch64) ARCH=aarch64 ;; x86_64|amd64) ARCH=x64 ;; *) echo "unsupported CPU"; exit 1 ;; esac
  echo "    downloading JDK $JAVA_VERSION ($OS/$ARCH)..."
  curl -fsSL -o "$TOOLS/jdk.tar.gz" \
    "https://api.adoptium.net/v3/binary/latest/$JAVA_VERSION/ga/$OS/$ARCH/jdk/hotspot/normal/eclipse"
  mkdir -p "$TOOLS/jdk" && tar -xzf "$TOOLS/jdk.tar.gz" -C "$TOOLS/jdk" --strip-components=1
  rm "$TOOLS/jdk.tar.gz"
fi

# ---------- 3. jadx ----------
echo "==> jadx"
if [ ! -x "$TOOLS/jadx/bin/jadx" ]; then
  echo "    downloading jadx $JADX_VERSION..."
  curl -fsSL -o "$TOOLS/jadx.zip" \
    "https://github.com/skylot/jadx/releases/download/v$JADX_VERSION/jadx-$JADX_VERSION.zip"
  mkdir -p "$TOOLS/jadx" && unzip -qo "$TOOLS/jadx.zip" -d "$TOOLS/jadx"
  rm "$TOOLS/jadx.zip"
  chmod +x "$TOOLS/jadx/bin/jadx"
fi
# Wrapper that points jadx at the local JDK when there is one
cat > "$TOOLS/bin/jadx" <<'EOF'
#!/bin/sh
TOOLS="$(cd "$(dirname "$0")/.." && pwd)"
for home in "$TOOLS/jdk/Contents/Home" "$TOOLS/jdk"; do
  [ -x "$home/bin/java" ] && export JAVA_HOME="$home" && break
done
exec "$TOOLS/jadx/bin/jadx" "$@"
EOF
chmod +x "$TOOLS/bin/jadx"
echo "    $("$TOOLS/bin/jadx" --version)"

# ---------- 4. Sample APK + .env ----------
echo "==> Files"
if [ ! -f apks/InsecureShop.apk ]; then
  curl -fsSL -o apks/InsecureShop.apk "$APK_URL" && echo "    downloaded apks/InsecureShop.apk"
fi
if [ ! -f .env ]; then
  cp .env.example .env && echo "    created .env (add your API keys)"
fi

# ---------- 5. Smoke test ----------
echo "==> Test: ingest"
python main.py ingest

echo
echo "Done. Next: add OPENAI_API_KEY to .env, then: python main.py scan --model teacher"
