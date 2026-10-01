# Putting the Ontario model on GitHub

## What goes up and what stays on your PC
- **Goes up:** 114 files, about 2.4 MB in total.
  - All code (model/, the pull scripts, morning.py)
  - Notes and Model_Guide.md
  - The page template and the built page
  - The small learned rule/ladder CSVs
  - The .bat buttons
- **Stays on your PC** (blocked by .gitignore, and double-checked by tools/check_secrets.py before every commit):
  - **Credentials:** db.json, nrg.json, sv.json, any *key* or *secret* file.
  - **Large data:** cache/ (365 MB), archive/ (121 MB) and data/ (223 MB). The morning pulls rebuild these.
- **Credentials keep working without being uploaded:**
  - The scripts find db.json in this folder or in Documents\aeso-cushion model.
  - The scripts find nrg.json in this folder.
  - On a new PC, copy those 1-2 files into the same place by hand (USB, OneDrive, password manager). Never put them through GitHub.

## One-time setup (about 10 minutes)
1. **Install Git:** https://git-scm.com/download/win. Accept all the defaults.
2. **Install GitHub CLI:** https://cli.github.com. Download the Windows installer and run it.
3. Open a **new** Command Prompt so both tools are found.
4. **Log in to GitHub** (you do this yourself in the browser; nothing is saved here):
   ```
   gh auth login
   ```
   Pick **GitHub.com → HTTPS → Yes (authenticate Git) → Login with a web browser**, then enter the one-time code it shows.
5. **Optional:** if the repo should live under the Dynasty Power GitHub organization, check the org name with `gh org list`.
6. **Run the setup button.** Double-click **setup_github.bat** in this folder, or run it from the Command Prompt:
   ```
   cd /d "C:\Users\mabbasi\OneDrive - Dynasty Power\Desktop\Ontario-Cushion Model"
   setup_github.bat
   ```
   - When it asks for a repo name, type `ontario-cushion-model` for your own account, or `ORGNAME/ontario-cushion-model` for the company org.
   - It creates the repo as **private**, runs the secret check, commits and pushes.
7. **Check it:** run `gh repo view --web`. Confirm there is no db.json or nrg.json and no cache/ or archive/ folder.

## Every day after that
- Run morning.py as usual.
- When you or Claude change code or notes, double-click **save_to_github.bat**. Type a short description, and it checks for secrets, commits and pushes.

## If something goes wrong
- **"STOPPED: these staged files look like credentials"**: the check worked and nothing was uploaded.
  1. Run `git rm --cached <that file>`.
  2. Add its name to .gitignore.
  3. Run the button again.
- **Push rejected or not logged in:** run `gh auth login` again.
- **OneDrive:** keeping the .git folder inside OneDrive is fine. If OneDrive shows sync conflicts on .git files, pause OneDrive while pushing.
- **If a credential ever reaches GitHub:** change that password straight away. Deleting the file does not remove it from the repo's history.
