# Contributing

`main` only changes through pull requests. Direct pushes are blocked by branch
protection, and the `ci` check must pass before a merge.

## Flow

1. Branch from `main`:
   `feat/<topic>`, `fix/<topic>`, `docs/<topic>`, `refactor/<topic>`,
   `chore/<topic>` or `release/vX.Y`.
2. Commit with [Conventional Commits](https://www.conventionalcommits.org/):
   `type(scope): subject`, imperative, at most ~72 characters.
   Scopes in use: `common`, `mako`, `murasame`, `yoshino`, `lena`, `sub`,
   `r18`, `tl`, `mt`, `gui`, `tools`, `pipeline`, `font`, `readme`, `progress`.
3. Open a PR into `main` and fill in **Verification** with the command you ran
   and its result.
4. Merge with **Create a merge commit** (no squash, no rebase). `main`'s
   first-parent history then reads as one line per PR.

## Releases

Open a `release/vX.Y` branch, merge it, then tag the merge commit `vX.Y` and
attach the installer zip to the GitHub release.
