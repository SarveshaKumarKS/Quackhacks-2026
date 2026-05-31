# Note on the Accidental Push Attempt

## Summary

An attempted `git push` to this repository surfaced under the GitHub account
**`SanthoshBaradwaj`**. This was **not** an intentional push by Santhosh — it
happened because I was working on **Santhosh's laptop because I had borrowed it for the hackathon**, which still had his
GitHub credentials cached in git / the OS credential store.

When I ran the push, git used those saved credentials, so the request appeared
to come from `SanthoshBaradwaj`. After i realized that this happened we made sure that this did not happen again.

## What this was for

This was just one commit and only for a small set of UI changes — roughly **367 lines of code** —
for the floating mascot widget work. It was a local commit on a feature branch,
not a change to `main`, and we even removed and modified this UI

## Clarification

- The push attempt originated from a **shared/borrowed machine**, not from
  Santhosh deliberately pushing to this repo.
- The cached credentials belonged to the laptop's owner, not to the intended
  author of the change.
- No code was merged or pushed; the remote repository is unchanged.

## Action taken

- No further push attempts were made.
- The credentials issue is noted so it can be cleared from the borrowed laptop
  (Windows Credential Manager → `git:https://github.com`).
