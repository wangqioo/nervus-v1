#!/bin/bash
# Nervus 平台测试入口
# 用法：bash tests/run_tests.sh [--with-cloud]

set -e
cd "$(dirname "$0")/.."

echo "========================================"
echo "  Nervus Platform 测试套件"
echo "========================================"

PASS=0
FAIL=0
# bash 3 兼容的计数
inc_pass() { PASS=$((PASS + 1)); }
inc_fail() { FAIL=$((FAIL + 1)); }

run_test() {
    local name="$1"
    shift
    echo ""
    echo "--- $name ---"
    if python "$@"; then
        echo "  [PASS] $name"
        inc_pass
    else
        echo "  [FAIL] $name"
        inc_fail
    fi
}

# ── 无需网络的测试 ────────────────────────────
run_test "ModelService 配置加载" tests/test_model_service.py config


# ── 需要 Arbor 运行的测试 ─────────────────────
if curl -sf "${ARBOR_URL:-http://localhost:8090}/healthz" > /dev/null 2>&1; then
    run_test "SDK LLM chat" tests/test_sdk_llm.py chat
    run_test "SDK JSON 模式" tests/test_sdk_llm.py json
    run_test "SDK embed" tests/test_sdk_llm.py embed
else
    echo ""
    echo "--- SDK 测试 [SKIP] --- (Arbor 未运行，docker compose up 后重试)"
fi

# ── 云端模型测试（需要 API Key）───────────────
if [ "$1" = "--with-cloud" ]; then
    if [ -n "$DEEPSEEK_API_KEY" ]; then
        run_test "DeepSeek Chat" tests/test_model_service.py cloud deepseek-chat
    fi
    if [ -n "$ANTHROPIC_API_KEY" ]; then
        run_test "Claude Sonnet" tests/test_model_service.py anthropic claude-sonnet-4-6
    fi
    if [ -n "$ZHIPUAI_API_KEY" ]; then
        run_test "GLM-4 Flash" tests/test_model_service.py cloud glm-4-flash
    fi
fi

# ── 状态检测 ─────────────────────────────────
run_test "模型状态检测" tests/test_model_service.py status

echo ""
echo "========================================"
echo "  结果: ${PASS} 通过 / ${FAIL} 失败"
echo "========================================"

[ $FAIL -eq 0 ] && exit 0 || exit 1
