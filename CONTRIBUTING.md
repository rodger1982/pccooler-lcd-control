# Contributing

Thank you for contributing to PCCOOLER-LCD Control.

## Development workflow

1. Fork or clone the repository.
2. Create a focused branch:
   ```bash
   git switch -c fix/descriptive-name
   ```
3. Make and test the change.
4. Commit with a clear message.
5. Push the branch and open a pull request.

## Linux setup

On Arch Linux:

```bash
makepkg -Csi
```

Run from the installed package:

```bash
pccooler-lcd-control
```

## Windows setup

Use 64-bit Python 3.12 and PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\windows\run-development.ps1
```

Build the portable application and installer:

```powershell
.\windows\build-windows.ps1
```

## Reporting bugs

Include:

- Operating system
- Application version
- LCD model and USB/COM details
- Exact steps to reproduce
- Terminal output or service logs
- Relevant layout file when possible

## Code style

Keep platform-specific code isolated. Shared rendering, layout, and theme code
should remain usable on both Linux and Windows.
