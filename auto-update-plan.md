# ClipABit Auto-Update Plan

Two approaches for automatically updating the plugin in-place, without requiring users to re-download and re-run the installer.

Both approaches share the same **version check + download** mechanism and differ only in **how the file swap happens**.

---

## Shared: Version Check & Download

### Prerequisites

- Add `__version__ = "1.0.0"` to `clipabit.py` (or a separate `version.py`)
- Bump version in both `pyproject.toml` and `__version__` on each release
- Attach a `clipabit-plugin-vX.Y.Z.zip` asset to each GitHub Release containing just the plugin files (`clipabit.py`, `version.py`, `assets/`, `clipabit/`, `scripts/`)
- Include a `SHA256SUMS` file in the release for download verification

### Version check flow

1. On plugin startup, spawn a background `QThread`
2. Call `GET https://api.github.com/repos/OWNER/REPO/releases/latest`
3. Compare `tag_name` against local `__version__`
4. If newer: download the `.zip` asset, verify SHA256 hash, extract to a temp staging directory
5. Hand off to the file swap strategy (A or B)

---

## Approach A: Deferred Swap (Recommended)

**Concept:** Download the update now, apply it the next time the plugin loads.

### How it works

1. **Download phase** (runs in background thread during current session):
   - Fetch the plugin `.zip` from GitHub Releases
   - Verify SHA256 hash
   - Extract to `<plugin_install_dir>/.clipabit-pending-update/`
   - Write a marker file `<plugin_install_dir>/.update-pending` containing the new version string

2. **Apply phase** (runs at the very top of `clipabit.py` on next launch):
   - Before any imports, check if `.update-pending` marker exists
   - If yes: back up current files to `.clipabit-backup/`, then copy files from `.clipabit-pending-update/` over the current installation
   - Delete the marker and pending directory
   - Continue loading the plugin (now running the new version)

3. **User notification:**
   - After download: show dialog saying "Update downloaded. It will apply next time you open DaVinci Resolve."
   - After apply: optionally show a "Successfully updated to vX.Y.Z" message on next launch

### Implementation steps

1. [ ] Add `__version__` constant to `clipabit.py`
2. [ ] Create `UpdateChecker` QThread class
   - Check GitHub Releases API for latest version
   - Compare with local `__version__`
   - Download and verify `.zip` if newer
   - Extract to `.clipabit-pending-update/`
   - Write `.update-pending` marker
   - Emit `update_ready` signal
3. [ ] Add `_apply_pending_update()` function at the top of `clipabit.py`
   - Check for `.update-pending` marker
   - Back up current files to `.clipabit-backup/`
   - Copy pending files over current installation
   - Clean up marker and pending directory
4. [ ] Add `_on_update_ready()` slot in `ClipABitApp` to show notification dialog
5. [ ] Wire up `UpdateChecker` in `ClipABitApp.__init__()`
6. [ ] Update GitHub Release workflow to include a `clipabit-plugin-vX.Y.Z.zip` asset with just the plugin files
7. [ ] Add SHA256 hash verification for downloaded zip
8. [ ] Test on both macOS and Windows

### Pros

- Simple — no external processes or OS-specific detach logic
- Safe — files are only swapped when they're not loaded/locked
- Rollback — backup directory allows recovery if update is broken
- No permission issues — files are written by the same process that read them

### Cons

- Update doesn't take effect until next launch
- User must restart DaVinci Resolve to get the new version

---

## Approach B: External Updater Process

**Concept:** Download the update now, launch a separate Python process that waits for DaVinci Resolve to close, then swaps the files.

### How it works

1. **Download phase** (same as Approach A):
   - Fetch the plugin `.zip` from GitHub Releases
   - Verify SHA256 hash
   - Extract to a temp staging directory

2. **Spawn updater** (runs when user confirms the update):
   - Write a small standalone Python script (`clipabit_updater.py`) to a temp directory
   - The script contains hardcoded paths for source (staging) and target (install dir)
   - Launch it as a detached process that survives after DaVinci Resolve closes
   - On Windows: use `subprocess.Popen` with `DETACHED_PROCESS` creation flag
   - On macOS: use `subprocess.Popen` with `start_new_session=True`

3. **Updater script logic:**
   - Wait for DaVinci Resolve process to exit (poll process list)
   - Back up current plugin files
   - Copy staged files to the plugin directory
   - Clean up staging directory and self-delete

4. **User notification:**
   - Show dialog: "Update will be applied after DaVinci Resolve closes."
   - On next launch, show "Updated to vX.Y.Z" if a `.update-applied` marker exists

### Implementation steps

1. [ ] Add `__version__` constant to `clipabit.py`
2. [ ] Create `UpdateChecker` QThread class (same as Approach A)
3. [ ] Create `_generate_updater_script()` method
   - Generates a standalone Python script as a string
   - Script polls for DaVinci Resolve process exit
   - Script copies files from staging to install directory
   - Script writes `.update-applied` marker on success
   - Script cleans up staging dir and self-deletes
4. [ ] Add platform-specific process detach logic
   - Windows: `subprocess.Popen(..., creationflags=subprocess.DETACHED_PROCESS)`
   - macOS: `subprocess.Popen(..., start_new_session=True)`
5. [ ] Add `_on_update_ready()` slot to prompt user and launch updater
6. [ ] Add startup check for `.update-applied` marker to show success message
7. [ ] Update GitHub Release workflow to include plugin `.zip` asset
8. [ ] Add SHA256 hash verification for downloaded zip
9. [ ] Test on both macOS and Windows
10. [ ] Handle edge cases:
    - User doesn't close Resolve for a long time (updater timeout?)
    - Multiple updater processes spawned
    - Updater crashes mid-copy (rollback from backup)

### Pros

- Update applies as soon as Resolve closes — no manual restart needed
- Can swap all files including the main entry point

### Cons

- More complex — OS-specific process management
- Risk of orphaned updater processes
- File lock issues if Resolve doesn't fully release files
- Harder to debug (detached process with no visible output)
- Security: writing and executing a dynamically generated script

---

## Recommendation

**Use Approach A (Deferred Swap)** unless there's a strong requirement for immediate updates. It's simpler, safer, and easier to maintain. The only tradeoff is that users need to restart Resolve, which is a reasonable ask.

---

## Security Checklist (Both Approaches)

- [ ] Verify SHA256 hash of downloaded zip before extracting
- [ ] Use HTTPS for all API calls and downloads
- [ ] Validate that the zip only contains expected file types (.py, .png, etc.)
- [ ] Sanitize extracted file paths to prevent zip slip attacks
- [ ] Back up current files before overwriting
- [ ] Don't execute any code from the downloaded zip until it's verified
