# Employee Performance Analyzer and Recommendation System (EPARS)

To copy repo use this command: `git clone https://github.com/Aarsh-J/EPARS.git`

### Documentation
- [`docs/instructions.md`](docs/instructions.md) — day-to-day setup/run commands
- [`docs/SUPABASE.md`](docs/SUPABASE.md) — shared DB details, keeping it running, common bugs & fixes
- [`docs/plan.md`](docs/plan.md) — deployment plan (DB, backend, frontend hosting)
- [`docs/dataset_schema.md`](docs/dataset_schema.md) — full dataset/table schema spec
- [`epars_agent/README.md`](epars_agent/README.md) — backend tools & agent setup
- [`epars_policies/README.md`](epars_policies/README.md) — RAG policy embedding setup

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
