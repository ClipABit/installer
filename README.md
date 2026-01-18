# Installer Repo

Before running, make sure to install the venv on your local device by running

```bash
cd frontend/plugin
uv venv
```

In order to build the package, turn build-pkg.sh and postinstall into an executable, and run it:

```bash
chmod +x build-pkg.sh scripts/postinstall
./build-pkg.sh
```

This creates: `dist/ClipABit-Installer.pkg`
You can then open the pkg by double clicking on it.

Current workaround: If it doesn't install the files in the desired folder, run:

```bash
sudo dist/ClipABit.pkg
```

This is the pkg builder base command used in build-pkg.sh:

```bash
pkgbuild --root frontend/plugin --install-location /Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility / --identifier com.clipabit.plugin.installer --version 1 ClipABit.pkg
```

Check if the plugin was installed successfully:

```bash
# Check if plugin directory exists
ls -la ~/Library/Application\ Support/Blackmagic\ Design/DaVinci\ Resolve/Fusion/Scripts/Utility/ClipABit/
```

To do:
Github actions setup
Find out why it only works when you run it with sudo
Figure out venv
