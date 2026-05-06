# Git SSH Authentication for ahfl-working-Gpu

**IMPORTANT:** Always use SSH to push code to this repository. HTTPS + PAT tokens have authentication issues.

## Quick Start

```bash
# Set SSH remote (one time only)
git remote set-url origin git@github.com:Tusharj-habilelab/ahfl-working-Gpu.git

# Verify it's set correctly
git remote -v

# Push normally
git push
```

## Why SSH?

- ✅ No token expiration
- ✅ No credentials needed after setup
- ✅ More secure
- ✅ Automatic authentication

## SSH Key Setup (if needed)

```bash
# Generate SSH key (if not exists)
ssh-keygen -t ed25519 -C "your-email@example.com"

# Add to GitHub: https://github.com/settings/keys
cat ~/.ssh/id_ed25519.pub
```

## Test SSH Connection

```bash
ssh -T git@github.com
# Should output: "Hi Tusharj-habilelab! You've successfully authenticated..."
```

## Troubleshooting

**If push fails with "Authentication failed":**
```bash
# Verify remote is SSH
git remote -v

# Should show: git@github.com:Tusharj-habilelab/ahfl-working-Gpu.git
# NOT: https://github.com/...
```

---

**Last updated:** 5 May 2026  
**Contributor:** GitHub Copilot
