# Contributing to OAK

Thank you for helping make OAK safer and easier to audit. Contributions are welcome for bug fixes, tests, documentation, accessibility, security hardening, and small operational improvements.

## Before opening a change

1. Search existing issues and pull requests.
2. Open an issue for behavior changes or new trading rules so the invariant and acceptance criteria are explicit.
3. Never include account credentials, Telegram tokens, broker data, runtime logs, or private profile files.
4. Keep real-order submission outside the default path. Advisory output must continue to require direct user confirmation.

## Local development

OAK targets Windows and Python 3.12 or newer. Create a virtual environment, then install the project requirements:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run the regression suite before every pull request:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

For dashboard changes:

```powershell
cd dashboard
npm ci
npm run build
```

## Pull request expectations

- Explain the root cause, user impact, and exact validation performed.
- Add a failing regression test before a production-code fix when practical.
- Keep the patch surgical and avoid unrelated formatting or generated files.
- Update both Vietnamese and English documentation when public behavior changes.
- Confirm that no secret or customer data is present in the diff.

Maintainers may ask for smaller commits, additional tests, or a security review before merging.
