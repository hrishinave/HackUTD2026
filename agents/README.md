# Setting up a laptop

Each of the four laptops does this once. Pick your role first: **C** Client, **E** Engine, **D** Data, **W** Web + integrator. What each role does is in `agents/PROJECT.md`.

```bash
git clone https://github.com/hrishinave/HackUTD2026.git
cd HackUTD2026
git fetch --tags && git tag -l 'gate/*'        # should list gate/G0-bootstrap

ROLE=E                                          # change to C, E, D or W
BRANCH=engine                                   # client, engine, data or web
cp agents/roles/$ROLE/CLAUDE.md CLAUDE.md       # for Claude Code
cp agents/roles/$ROLE/AGENTS.md AGENTS.md       # for Codex
git checkout -b $BRANCH

cp .env.example .env                            # paste the keys and tokens from the team chat
pip install -r server/requirements.txt
git status                                      # CLAUDE.md, AGENTS.md and .env must NOT appear (gitignored)
```

Then open Claude Code or Codex in the repo folder and say: "Read CLAUDE.md (or AGENTS.md) and the files it lists, then start my first task." The agent knows its role, its files, its gates and when to stop and wait.

| Person | Role | Branch | First task | First gate it waits on |
|---|---|---|---|---|
| Hrishi | C | `client` | C1 at 0:30 (on the demo laptop, glasses paired) | `gate/E1-server` for the socket test in C2 |
| Prakrit | E | `engine` | E1 at 0:30 | `gate/D1-legacy` for E2 |
| AK | D | `data` | D1 at 0:30 | `gate/E1-server` for the `/api/simulate` route in D2 |
| Keshav | W | `web` | Tokens and keys to the chat, Task 0, then W1 (bootstrap is already done) | `gate/E1-server` for the events API in W2 |

If a role file changes on `main`, copy it again (`cp agents/roles/$ROLE/CLAUDE.md CLAUDE.md` and the same for `AGENTS.md`).
