# PCCOOLER-LCD Control 3.0.0 Beta 5

Beta 5 fixes the layout media-validation and popup-loop regression.

Only the layout's top-level wallpaper is validated. Widget background colors,
such as `#060608`, are treated strictly as colors.

If media is missing or cannot be decoded:

- the layout still opens,
- the app stays usable,
- a single status-bar warning is shown,
- the fallback background color is rendered,
- the user can browse to a replacement and save the layout.

## Update GitHub

```fish
cd ~/coding-projects/pccooler-project

rsync -av --delete \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='.venv-win' \
  --exclude='build' \
  --exclude='dist' \
  pccooler-lcd-control-3.0.0-beta5/ \
  pccooler-lcd-control/

cd pccooler-lcd-control
git add .
git commit -m "Fix layout media validation and popup loop"
git push origin main
```

## Install on Arch Linux

```fish
makepkg -Csi
```
