#!/bin/bash
# deploy.sh - Deploy music-creator-agent to a2hmarket
#
# Usage:
#   ./deploy.sh --shop <shopId> --version <version>
#
# Example:
#   ./deploy.sh --shop 123 --version 1.0.0

set -e

# Parse arguments
SHOP_ID=""
VERSION=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --shop)
            SHOP_ID="$2"
            shift 2
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --help)
            echo "Usage: ./deploy.sh --shop <shopId> --version <version>"
            exit 0
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

if [ -z "$SHOP_ID" ] || [ -z "$VERSION" ]; then
    echo "Error: --shop and --version are required"
    echo "Usage: ./deploy.sh --shop <shopId> --version <version>"
    exit 1
fi

# Get the Git repository URL
GIT_URL=$(git remote get-url origin 2>/dev/null || echo "")

if [ -z "$GIT_URL" ]; then
    echo "Error: No git remote 'origin' found. Please add a remote first:"
    echo "  git remote add origin https://github.com/xemaya/music-creator-agent.git"
    exit 1
fi

echo "========================================="
echo "  Deploying Music Creator Agent"
echo "========================================="
echo "  Shop ID:   $SHOP_ID"
echo "  Version:   $VERSION"
echo "  Git URL:   $GIT_URL"
echo "========================================="
echo ""

# Check if a2h-shopdiy CLI is available
if command -v a2h-shopdiy &> /dev/null; then
    echo "Submitting agent to a2hmarket..."
    a2h-shopdiy agent:submit \
        --shop "$SHOP_ID" \
        --source "$GIT_URL" \
        --version "$VERSION"
else
    echo "a2h-shopdiy CLI not found. Please install it first:"
    echo ""
    echo "  cd /Users/huanghaibin/AWS_WORKSPACE/agent-kit/a2h-agent-kit"
    echo "  python3 -m venv .venv"
    echo "  .venv/bin/pip install -e agent-sdk -e cli"
    echo ""
    echo "Then run this script again."
    exit 1
fi

echo ""
echo "Deployment complete!"
echo "You can view your agent at: https://a2hmarket.ai/shops/$SHOP_ID"
