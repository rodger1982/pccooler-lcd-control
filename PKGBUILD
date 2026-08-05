pkgname=pccooler-lcd-control
pkgver=3.0.0b14
pkgrel=1
provides=('pccooler-lcd')
conflicts=('pccooler-lcd')
replaces=('pccooler-lcd')
pkgdesc="Cross-platform control and layout designer for PCCOOLER CP3 LCD displays"
arch=('any')
license=('MIT')
depends=('ffmpeg' 'python' 'python-pyserial' 'python-psutil' 'python-pillow' 'pyside6')
makedepends=('python-build' 'python-installer' 'python-wheel' 'python-setuptools')
source=()
sha256sums=()

build() {
  cd "$startdir"
  rm -rf build dist app/*.egg-info
  python -m build --wheel --no-isolation
}

check() {
  cd "$startdir"
  PYTHONPATH=app python -m unittest discover -s tests -v
}

package() {
  cd "$startdir"
  python -m installer --destdir="$pkgdir" "dist/pccooler_lcd_control-${pkgver}-py3-none-any.whl"
  install -Dm644 packaging/99-pccooler-lcd.rules "$pkgdir/usr/lib/udev/rules.d/99-pccooler-lcd.rules"
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
  install -Dm644 README.md "$pkgdir/usr/share/doc/$pkgname/README.md"

  install -Dm644 assets/branding/logo.png "$pkgdir/usr/share/pccooler-lcd-control/branding/logo.png"
  install -Dm644 assets/branding/splash.png "$pkgdir/usr/share/pccooler-lcd-control/branding/splash.png"
  install -Dm644 assets/branding/github-banner.png "$pkgdir/usr/share/doc/$pkgname/github-banner.png"
  for size in 16 32 48 64 128 256 512; do
    install -Dm644 "assets/icons/pccooler-lcd-control-${size}.png"       "$pkgdir/usr/share/icons/hicolor/${size}x${size}/apps/pccooler-lcd-control.png"
  done
  install -Dm644 packaging/pccooler-lcd-control.desktop "$pkgdir/usr/share/applications/pccooler-lcd-control.desktop"
  install -Dm644 packaging/pccooler-lcd-control.service "$pkgdir/usr/lib/systemd/user/pccooler-lcd-control.service"
  install -d "$pkgdir/usr/share/pccooler-lcd/themes"
  cp -a themes/. "$pkgdir/usr/share/pccooler-lcd/themes/"
}
