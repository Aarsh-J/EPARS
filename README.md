# Employee Performance Analyzer and Recommendation System (EPARS)

To copy repo use this command: `git clone https://github.com/Aarsh-J/EPARS.git`

### Branch rules
- **develop** : Current working branch with our changes being pushed to it
- **prod** : Final Branch, develop will be merged when a feature is complete and tested
- **preprocessor** : Branch containing our Dataset generation code and our ML Model code (we will copy the complete ML model to main branches, tweeking will be done here)

#### Try using proper branch naming conventions and commit messages for clearity 

### Git Commands
- `git branch` : List out existing branches
- `git branch <branch_name>` : Create ew branch from your current branch (but you dont move to the created branch)
- `git branch -d <name>` : delete branch
- `git branch -m <old-name> <new-name>` : rename branch
  
- `git checkout <branch_name>` : move to existing branch
- `git checkout -b <branch_name>` : create new branch (from your current branch) and open that 
- `git checkout --orphan <branch_name>` : create new branch with no parent

- `git pull <branch-name>` : pull branch to yor current (existing in your device/local)
- `git pull origin <branch-name>` : pull branch from git to yor current

- `git commit -m "[message]"` : commit
- `git push origin <branch-nae>` : pushes/merges your branch to specified one in git
# EPARS — Employee Performance Analyzer and Recommendation System

Clone: `git clone https://github.com/Aarsh-J/EPARS.git`

## This branch (`ui-changes`)

This branch holds the **frontend**, a React app in [frontend/](frontend/) that talks to
the backend over a REST API — it no longer contains any Python/Flask code or ML model
code (those live on other branches, see below).

- **Setup, dev server, build:** see [frontend/README.md](frontend/README.md)
- **Migration history, API contract the backend must implement, deployment plan:**
  see [plan.md](plan.md)

## Other branches

- **`dev-backend`** : the Python backend — LangGraph agent (`epars_agent/`) and the
  RAG/HR-policy subsystem (`epars_policies/`), backed by Supabase Postgres.
- **`preprocessor`** : dataset generation code and ML model training/artifacts.
- **`main`** / **`production`** : integration branches — features get merged in once
  built and tested on their own branch.

### Git Commands
- `git branch` : List out existing branches
- `git branch <branch_name>` : Create new branch from your current branch (but you dont move to the created branch)
- `git branch -d <name>` : delete branch
- `git branch -m <old-name> <new-name>` : rename branch

- `git checkout <branch_name>` : move to existing branch
- `git checkout -b <branch_name>` : create new branch (from your current branch) and open that
- `git checkout --orphan <branch_name>` : create new branch with no parent

- `git pull <branch-name>` : pull branch to your current (existing in your device/local)
- `git pull origin <branch-name>` : pull branch from git to your current

- `git commit -m "[message]"` : commit
- `git push origin <branch-name>` : pushes/merges your branch to specified one in git
