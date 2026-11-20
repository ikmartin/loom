# A fence for Lean and TeX on macOS (v0.1 study, raw, the fence trial)

Investigator: fence trial, for the Formalization row of plan 0.32 and what is left of SEC-3. Machine: macOS 26.5.2 (build 25F84) on arm64, 8 cores, 16 GB, shared with another session running test lanes, so the one-minute load average stood between 1.5 and 23 and **every timing below is indicative**. Done on 2026-11-19 from 17:30, and finished on 2026-11-20 after a pause. Lean `leanprover/lean4:v4.36.0-rc2` under `~/.elan` through Homebrew's elan 4.2.4 (both from the earlier trial), Mathlib `9d581dfff2e4`. TeX Live 2024 at `/usr/local/texlive/2024` (pdfTeX 1.40.26, kpathsea 6.4.0, latexmk 4.86a, biber 2.20, make4ht 0.4b). Xcode is installed and selected (`xcode-select -p` is `/Applications/Xcode.app/Contents/Developer`). Loom at `b563e6b7`, read and not run, except one function called to write its TeX4ht configuration. Paths starting `$F/` are under `/private/tmp/claude-501/-Users-isaac-dev-loom-arras/f0ec29b5-fd45-4e3f-ae50-d9f9d632cd2f/scratchpad/fence-trial/`, where every profile, script, project and log of the trial is.

Every fact is marked **measured** (done here, on this machine, today) or **read** (from a file, a manual or a binary's strings, not tried). The decoy home is `$F/decoy-home`, holding `secret.txt` and `secret.tex` with the text `DECOY-SECRET-7f3a9c`; every run was given it as `HOME`. The second scratch folder every escape tried to write into is `$F/outside`. The one real file read was `/etc/hosts` (594 characters; its contents are not reported) and the one real existence check was `~/.zshenv`.

## Headline findings

- **FENCE-1. `sandbox-exec` fences both, for an ordinary user, with no root, no signing and no install.** Lean's certifying check (a clean rebuild of the module holding the declaration, `#print axioms` from a probe file, `leanchecker` replay) ran under a deny-by-default profile of six statements and three paths (the project, the one toolchain, the developer tools' `git`) and gave the same result as unfenced: build `Build completed successfully (18179 jobs)`, axioms `[propext, Classical.choice, Quot.sound]`, replay exit 0. A TeX compile of the showcase paper ran under a profile of six statements in four forms, pdflatex with bibtex, pdflatex with biber, make4ht, and a document whose font METAFONT must draw, and wrote byte-identical `.aux`, `.bbl` and `.html` to the unfenced runs. Both profiles are in this report in full (sections 2 and 3). **measured**
- **FENCE-2. Every escape failed under the fence; without it every one succeeded or only TeX's own settings stopped it.** Lean: 14 attempts from `#eval` in a module the build compiles (read the decoy secret, list the decoy home, read `/etc/hosts`, see `~/.zshenv`, list `~/.cache/mathlib`, write outside, spawn `cat` and `sh`, a TCP connection from Lean's own socket API, `nc`, a name lookup, a launchd job, the pasteboard, the user's preferences, the process list): 14 of 14 succeeded unfenced, 0 of 14 fenced. TeX: 16 attempts in pdflatex and 4 in lualatex, each with shell escape off, restricted and on, and with kpathsea as loom sets it and fully open: under the final profile nothing was read outside the allowed places, nothing was written outside the run's folder and TeX's font cache, and no connection, name lookup or launchd job was made. **measured**
- **FENCE-3. The network is shut wholly, name lookups and launchd included, which file rules alone would not do.** `deny default` refused `network-outbound` to `1.1.1.1:80` (from Lean's own socket, `nc`, LuaTeX's socket library), refused the socket to `mDNSResponder` (so `github.com` and `example.com` did not resolve), refused `job-creation` (so `launchctl submit` could not start a job outside the fence, which unfenced it did and wrote outside), refused the pasteboard and preference daemons, and refused executing set-uid programs (`ps`). **measured**
- **FENCE-4. What each tool needs beyond its own folder is small but not guessable, and two of the needs come from Apple's developer-tool shims.** Lean needs `/private/etc/gitconfig` (Lake runs `git` on every build) and a real `git`: `/usr/bin/git` is an `xcrun` shim that needs the developer folder and `xcrun`'s cache in the per-user temporary folder, so the profile puts the developer folder's own `git` first on `PATH` instead. Through elan it also needs `/private/etc/ssl` (elan links Apple's libcurl, whose LibreSSL dies with "Auto configuration failed" without `openssl.cnf`) and elan's own installation; calling the toolchain's `lake` directly needs neither. Lean writes nothing outside the project. TeX needs the TeX tree, `TEXMFVAR` (read, and write under `fonts/` for METAFONT's bitmaps), `TEXMFHOME` (read), a writable copy of biber's unpack folder (FENCE-12), `/bin` and `/usr/bin` (the font scripts), and the developer folder with `xcrun`'s cache (read only), because of FENCE-5. **measured**
- **FENCE-5. TeX Live 2024's biber runs Apple's `lipo` on every run, so it needs the developer tools, fenced or not.** The universal `biber` calls `/usr/bin/xcode-select -p` and then `/usr/bin/lipo -extract_family arm64 -output …/thin/biber` each time it starts (the thin binary's time changed on every run); `lipo` is an `xcrun` shim. Fenced without the developer folder it said "Command Line Tools are not installed - run 'xcode-select --install'"; without `xcrun`'s cache it took 16.6 s against 7.7 s and 148 refusals while `xcodebuild` searched; with the cache readable it ran at its usual cost. Its own strings say a Mac without the tools cannot run it at all, which would matter to Install. **measured** (the calls), **read** (a Mac without the tools; TeX Live 2026's biber was not tried)
- **FENCE-6. kpathsea already stops TeX's own writes and nothing else.** With loom's `openout_any=p` every `\openout` outside the folder failed, also under shell escape on. With `openin_any` left at TeX Live's `a`, a document read the decoy secret into its log and PDF, opened `/etc/hosts` and saw `~/.zshenv`, under every shell-escape mode; LuaTeX's `io.open` read the secret with shell escape off; with shell escape on, a document copied the secret, wrote outside, connected out, resolved names and started a launchd job. `openin_any=p` blocked pdflatex's reads on TeX Live 2024 but made lualatex fail at once (luaotfload cannot read its own cache), and TeX Live 2026 ignores the setting. **measured** on 2024; **read** for 2026 (`loom/src/loom/tex/runner.py`, plan 0.32's Security row)
- **FENCE-7. The fence costs no time that could be measured, plus 0.9–3.2 s to clone biber's folder for a run that uses it.** In alternating pairs, the CPU time of pdflatex with bibtex, pdflatex with biber, make4ht, a no-op `lake build` and `#print axioms` was the same fenced and unfenced within the pairs' own spread; one replay pair took 16.4 s against 21.7 s. The machine's load (3 to 23, from another session) moved whole checks between 284 s and 635 s, fenced or not, so the wall clock says nothing finer. **measured**, on a loaded machine
- **FENCE-8. With no network a check that would need to fetch fails fast and plainly, but one that would need to compile Mathlib does not fail: it compiles.** A project without `.lake` failed in 3.4 s with `fatal: unable to access 'https://github.com/leanprover-community/mathlib4/': Could not resolve host: github.com`, leaving 80 KB. A `lean-toolchain` naming a toolchain that is not installed failed in 2.7 s with elan's `error: Operation not permitted (os error 1)` and wrote nothing under `~/.elan`. With one of Mathlib's built files moved aside, the fenced build compiled that module again (7 s) and passed; with all of them gone it would compile Mathlib for hours. `lake build --no-build` caught the missing file in 4 s with exit 3, so loom should run it first and refuse with a sentence. **measured** (the hours are **read**)
- **FENCE-9. A fence cannot be put up inside another one, so loom must start it from its own process, never from an agent's sandboxed shell.** `sandbox-exec` inside any restricting sandbox, deny-by-default or allow-by-default with writes denied, failed at once with `sandbox-exec: sandbox_apply: Operation not permitted` and exit 71; it nested only inside a profile that allowed everything. Claude Code's sandbox is itself a `sandbox-exec` profile (its binary carries `/usr/bin/sandbox-exec` and SBPL text), is off by default, and covers its Bash tool only, so a check started by loom's server (the MCP server or `loom serve`) is unaffected, and one started by a `loom` command the agent types in a sandboxed shell cannot fence itself. **measured** (nesting), **read** (Claude Code's sandbox and where it applies)
- **FENCE-10. "Deprecated" has meant, for fourteen years, no new API and nothing else.** The SDK's `sandbox.h` marks `sandbox_init` deprecated since macOS 10.8 and says the header "may be removed in a future release"; the manual page says to adopt App Sandbox. `/usr/bin/sandbox-exec` ships with this OS build (dated 24 June 2026), prints no warning, and runs the same profile language Apple's own daemons use (511 profiles under `/System/Library/Sandbox/Profiles`). Homebrew sandboxes its builds with it, and Claude Code its Bash tool. Apple offers nothing else to an unsigned command-line tool: App Sandbox needs a signature with entitlements and confines to a container and to what the person picks in a dialog, with fixed exception paths set at signing, so it cannot be told "this quilt's Lean folder" per run. **measured** (shipped, works, the profile count, Homebrew's and Claude Code's use), **read** (the header, App Sandbox's model)
- **FENCE-11. When the fence refuses something legitimate, what the person would see is wrong or opaque, so loom must say it itself.** The messages were: elan's "Auto configuration failed … openssl.cnf"; git's "unable to access '/etc/gitconfig': Operation not permitted"; elan's "Operation not permitted (os error 1)"; "Could not resolve host: github.com", which reads as being offline; biber's "Command Line Tools are not installed"; pdflatex's "Font bbm10 at 600 not found"; and, for a style kept where the profile does not let TeX look, presumably TeX's ordinary "not found" (no such style was tried; kpathsea's refused look into the decoy's `TEXMFHOME` printed nothing). Every refusal is in the unified log as `Sandbox: <process>(<pid>) deny(1) <operation> <path>`, readable by the person's own account with `log show`, so loom can name the path it refused. Matching log lines to one run is by time and process name, which mixed two runs here when they overlapped. **measured**
- **FENCE-12. What a fenced run may write outside its own folder is where a fence is soft, so the final profile writes nowhere that holds code, and gives biber a copy of its folder.** A place the fence lets a document write and an unfenced program later runs is a way out. A first profile let TeX write all of biber's unpack folder and `xcrun`'s cache: with kpathsea fully open, a fenced document wrote a file into the unpack folder, whose Perl modules the person's next unfenced biber loads, and could have rewritten `xcrun`'s cache, which says where `/usr/bin/git` and `/usr/bin/lipo` find the real programs. Made read-only, the unpack folder did not stop biber: biber silently unpacked a fresh 202 MB copy into the run's `TMPDIR` on every run (5.6 GB of them by the end of the trial), and failed outright when its standard output was a file outside the run ("run3(): Operation not permitted saving STDOUT"). The final profile, `tex8`, lets a run write only its own folder, into which loom clones the machine's unpack folder copy-on-write (`cp -c`, 0.9–3.2 s under load; APFS shares the blocks until one is written), and `TEXMFVAR/fonts` (bitmap fonts, which are data); `xcrun`'s cache is read-only. With loom's `openout_any=p` a document could write none of those places anyway. **measured** (the writes, the copies, the clone), **read** (what biber and `xcrun` later do with the files)

## 1. What macOS offers a command-line tool

| mechanism | needs | confines reads | confines writes | confines network | usable for loom |
|---|---|---|---|---|---|
| `sandbox-exec` with an SBPL profile (the Seatbelt sandbox) | nothing: `/usr/bin/sandbox-exec`, any user | yes, by path, subpath or pattern, metadata separately | yes | yes, by address, port, and Unix socket; with `deny default` also the Mach services behind name lookup, launchd, the pasteboard and preferences | **yes**, measured |
| `sandbox_init` and the private `sandbox_init_with_parameters` / `sandbox_apply` the tool calls | linking `libsystem_sandbox`, or Python's `ctypes` in the child before `exec` | the same engine | the same | the same | yes, the same as above without the separate binary; not tried |
| App Sandbox | a code signature with `com.apple.security.app-sandbox`, an app bundle or an embedded `Info.plist`; children inherit | to a container and what the person picks in an open panel, plus fixed exception paths baked in at signing | the same | yes (`network.client` absent) | no: loom's per-quilt paths cannot be granted per run, and it would mean re-signing or wrapping the toolchain. read |
| Containerization (`container`, macOS 26 on Apple silicon) | Apple's signed installer (an administrator's password once) and Linux builds of Lean, Mathlib and TeX | yes, by what is mounted | yes | yes | not for v0.1: a second 10 GB Lean and a second TeX inside Linux. read |
| Virtualization framework directly, Endpoint Security, a Network Extension filter, `pf`, another user account | an entitlement from Apple, root, or both | — | — | — | no. read |
| kpathsea's `openin_any`, `openout_any`, `shell_escape` | an environment variable | `openin_any=p` blocks pdflatex's absolute and parent paths on TeX Live 2024, breaks lualatex, and does nothing on 2026; at its default `a`, nothing, Lua's `io.open` included | `openout_any=p` blocks TeX's writes outside the folder, and Lua's with shell escape off (with it on, Lua wrote outside); nothing a shell command does | no | as a second layer only. measured on 2024 |
| `setrlimit` (`ulimit`) | nothing | no | file size only | no | for time and memory caps beside a fence |

SBPL is not documented by Apple. The profiles here use what Apple's own profiles use (`deny default`, `import "system.sb"`, `subpath`, `literal`, `regex`, `path-ancestors`, `param`, `string-append`) and were checked by running them. `(import "system.sb")` is the part "a process needs to start": dyld's shared cache in the cryptexes, `/System`, `/usr/lib`, `/usr/share`, `/dev/null` and `/dev/urandom`, `/etc/passwd`, `sysctl` reads, and a short list of Mach services (`opendirectoryd` for user lookups, `cfprefsd`, `logd`, `trustd`). Its header says it is Apple's private interface and may change without notice; importing it means a macOS update can change what the fence allows, in either direction.

Parameters go in with `-D KEY=VALUE` and are read with `(param "KEY")`, so a profile is a fixed file and a path is never pasted into its text, which keeps a quilt's path with a quote or a parenthesis from changing the profile. Paths must be the resolved ones: `getconf DARWIN_USER_TEMP_DIR` gives `/var/folders/…`, which matched nothing until it was passed as `/private/var/folders/…`. **measured**

## 2. Lean

### Setup

A Lake project at `$F/lean/Trial` with `lakefile.toml` requiring Mathlib at the exact revision of the earlier trial and `lean-toolchain` at `leanprover/lean4:v4.36.0-rc2`, so no new toolchain was fetched. One module, `Trial/Saturation.lean`, holds the earlier trial's `divergence`, `cycleLattice` and `cycleLattice_saturated` (its section 2), with a six-line proof, under `import Mathlib`. `lake update` took 69 s: it cloned Mathlib and its eight dependencies (57 MB of `.git` in all, Mathlib's 43 MB) and Mathlib's post-update hook ran the cache tool, which found all 9,080 files already in `~/.cache/mathlib` and downloaded nothing ("No files to download"; decompressing took 20 s). `lake exe cache get` run again by hand took 17 s and downloaded nothing. The project is 7.2 GB, 6.7 GB of it Mathlib's build (130,351 files). This was the trial's only network use outside the fence. **measured**

The certifying check, as loom would run it (`$F/scripts/leancheck`): remove the project's own `.lake/build`; `lake build Trial.Saturation`; `lake env lean .loom-probe/Axioms.lean`, a file holding `import Trial.Saturation` and `#print axioms Trial.cycleLattice_saturated`; `lake env leanchecker Trial.Saturation`. Each ran in an environment of five variables: `PATH`, `HOME` (the decoy), `ELAN_HOME=/Users/isaac/.elan`, `TMPDIR` (inside the project's `.lake`), `LANG`.

### How the profile was found

Each run started from `deny default` and `import "system.sb"`, and each refusal was read from the unified log (`log show --predicate 'eventMessage CONTAINS "Sandbox:"'`, as the person, no root). Then rules were taken away one at a time against a quick probe (a no-op `lake build`, which runs elan, Lake and git, and `lake env lean` on a one-line file), and the result checked with the full check. **measured**

| profile | added | outcome |
|---|---|---|
| `lean1` | read the project, `~/.elan`, Homebrew's elan, `/bin`, `/usr/bin`; ancestors' metadata; write the project | every step failed in 2–3 s: elan's LibreSSL could not read `/private/etc/ssl/openssl.cnf` ("Auto configuration failed") |
| `lean2` | `/private/etc/ssl` | Lake's `git` failed: `/usr/bin/git` is an `xcrun` shim, and with no developer folder it asked to install the Command Line Tools (`mach-lookup com.apple.dt.CommandLineTools.installondemand`) |
| `lean3` | the developer folder, `xcrun`'s cache (`$USERTMP/xcrun_db`), `~/.CFUserTextEncoding` | `git` failed: "unable to access '/etc/gitconfig': Operation not permitted" |
| `lean4` | `/private/etc/gitconfig` | **the full check passed**, with no refusal during build and replay |
| ablation | without `signal`, `process-info`, `/private/var/select`, `~/.CFUserTextEncoding`: each still passed; without `gitconfig`, `ssl` or `xcrun_db`: each failed | |
| `lean5` | `lean4` without the four unneeded rules and without `xcrun_db`, with the developer folder's own `git` first on `PATH` | **passed** |
| direct | `lean5` without Homebrew's elan and without `/private/etc/ssl`, calling the toolchain's `lake` directly | **passed** (refusals only of `~/.CFUserTextEncoding`, which git tolerates) |
| `lean6` | the direct form, reading one toolchain's folder instead of all of `~/.elan` | **the full check passed**: build 90.6 s, axioms 105.8 s, replay 87.5 s, at a load of 1.6 to 4.7; refusals only of git's `~/.CFUserTextEncoding` and of the trial's own wrapper `/usr/bin/env` |

`lean6`, the profile to build, in full. Its parameters for this machine were `PROJECT=$F/lean/Trial`, `TOOLCHAIN=/Users/isaac/.elan/toolchains/leanprover--lean4---v4.36.0-rc2`, `DEVDIR=/Applications/Xcode.app/Contents/Developer`, with `PATH=$TOOLCHAIN/bin:$DEVDIR/usr/bin:/usr/bin:/bin` and the toolchain's `lake` called by its full path. Loom reads `lean-toolchain` itself to find the folder, says plainly when it is not installed, and never runs elan, the only part of the chain that downloads.

```scheme
;; Lean's certifying check, fenced: one toolchain's lake, lean and leanchecker, called directly, and git from the developer tools.
;; Parameters: PROJECT (the Lake project), TOOLCHAIN (the toolchain lean-toolchain names, under elan's home), DEVDIR (the developer tools' Developer folder, for git).
(version 1)
(deny default)
(import "system.sb")
(allow process-exec process-fork)
(allow file-read* (subpath (param "PROJECT")) (subpath (param "TOOLCHAIN")) (subpath (param "DEVDIR")) (literal "/private/etc/gitconfig"))
(allow file-read-metadata (path-ancestors (param "PROJECT")) (path-ancestors (param "TOOLCHAIN")) (path-ancestors (param "DEVDIR")))
(allow file-write* (subpath (param "PROJECT")))
```

`lean5`, the profile that worked through elan (Homebrew's), in full, for a loom that keeps calling `lake` through elan. Its parameters were `PROJECT`, `ELAN=/Users/isaac/.elan`, `ELANBIN=/opt/homebrew`, `DEVDIR`, with `PATH=$DEVDIR/usr/bin:/opt/homebrew/bin:/usr/bin:/bin`.

```scheme
;; Lean's certifying check, fenced: the toolchain's lake, lean and leanchecker, and git from the developer tools.
;; Parameters: PROJECT (the Lake project), ELAN (elan's home), ELANBIN (the prefix elan's proxies live in), DEVDIR (the developer tools' Developer folder, for git).
(version 1)
(deny default)
(import "system.sb")
(allow process-exec process-fork)
(allow file-read* (subpath (param "PROJECT")) (subpath (param "ELAN"))
                  (subpath (string-append (param "ELANBIN") "/bin")) (subpath (string-append (param "ELANBIN") "/Cellar/elan-init"))
                  (subpath (param "DEVDIR"))
                  (subpath "/private/etc/ssl") (literal "/private/etc/gitconfig"))
(allow file-read-metadata (path-ancestors (param "PROJECT")) (path-ancestors (param "ELAN"))
                  (path-ancestors (param "ELANBIN")) (path-ancestors (param "DEVDIR")))
(allow file-write* (subpath (param "PROJECT")))
```

### What it writes besides the project

Nothing, fenced: the profile allows writes only inside the project and no write was refused during a passing check. Unfenced, elan writes `~/.elan/known-projects` (it lists the project's path; written at 17:33, by `lake update`), and nothing the check runs wrote there or under `~/.cache` afterwards. Lake's and Lean's temporary files go to `TMPDIR`, which the check set inside the project's `.lake`. **measured**

### No network, and a `.lake` that is absent or stale

| case | fenced result | time |
|---|---|---|
| project with no `.lake` (sources and `lake-manifest.json` only) | `info: mathlib: fetching revision '9d581dfff2e4…'` then `fatal: unable to access 'https://github.com/leanprover-community/mathlib4/': Could not resolve host: github.com` and `error: mathlib: failed to fetch the package revision`; exit 1; 80 KB left in `.lake` | 3.4 s |
| `lean-toolchain` names `leanprover/lean4:v4.99.0`, not installed | elan: `error: Operation not permitted (os error 1)`; exit 1; nothing written under `~/.elan` | 2.7 s |
| the project's own build removed (the check's normal case) | rebuilt, as above | see the timings |
| `lake build --no-build Trial.Saturation`, everything present | `All targets up-to-date (18179 jobs)`, exit 0 | 9 s |
| the same with Mathlib's `Order/Basic.olean` moved aside | `Some required targets logged failures: - Mathlib.Order.Basic`, exit 3, nothing built | 4 s |
| `lake build --no-build Mathlib`, everything present (the form the check needs, since it has just removed the project's own build) | `All targets up-to-date (18177 jobs)`, exit 0 | 10 s |
| a plain `lake build` with that file still missing | rebuilt `Mathlib.Order.Basic` inside the fence (2.7 s, byte-identical to the cached file, so nothing after it rebuilt) and succeeded | 7 s |

With no network a fenced build cannot fetch Mathlib's cache, so whatever of Mathlib's build is missing it compiles from source, inside the fence, as long as the timeout lets it: one module took seconds; a project whose Mathlib build is absent would compile all of Mathlib, which is hours (read, not tried). `lake build --no-build` tells the two apart in seconds with exit 3, so it is the check's first fenced step. The rebuilt module was compared with the moved file and the moved copy deleted. **measured**

### The escape attempts

`Trial/Escape.lean`, a module the build compiles, imports only `Lean` and runs each attempt in an `#eval` at elaboration time, which is what any agent-written module could do (`$F/lean/Trial/Trial/Escape.lean`; `lake build Trial.Escape`, 9–10 s).

| attempt | unfenced | fenced (`lean4`, and the same again under `lean6`) | the log's refusal |
|---|---|---|---|
| R1 read `decoy-home/secret.txt` | read the secret | `operation not permitted` | `file-read-data …/decoy-home/secret.txt` |
| R2 list the decoy home | 3 entries | refused | `file-read-data …/decoy-home` |
| R3 read `/etc/hosts` | 594 characters | refused | `file-read-data /private/etc/hosts` |
| R4 does `~/.zshenv` exist | true | false | `file-read-metadata /Users/isaac/.zshenv` |
| R5 list `~/.cache/mathlib` | 9,081 entries | refused | `file-read-data /Users/isaac/.cache/mathlib` |
| W1 write `$F/outside/lean-w1.txt` | written | refused | `file-write-create …/outside/lean-w1.txt` |
| S1 spawn `cat` on the secret | printed it | `cat: … Operation not permitted` | as R1 |
| S2 spawn `sh -c 'echo > outside'` | written | `Operation not permitted` | `file-write-create …/outside/lean-s2.txt` |
| N1 Lean's own TCP socket (`Std.Internal.UV.TCP`) to `1.1.1.1:80` | connected | `operation not permitted` | `network-outbound remote:*:80` |
| N2 `nc -z 1.1.1.1 80` | succeeded | exit 1 | `network-outbound remote:*:80` |
| N3 `dscacheutil` lookup of `example.com` | four addresses | none | `network-outbound /private/var/run/mDNSResponder`, `file-read-data /private/etc/hosts` |
| L1 `launchctl submit` a job writing outside | the job ran and wrote (removed after) | exit 1, no job | `job-creation` |
| P1 `pbpaste` | 126 characters (not shown) | exit 1, nothing | `mach-lookup com.apple.pasteboard.1` |
| P2 `defaults read -g AppleLocale` | `en_US` | "does not exist" | `user-preference-read kcfpreferencesanyapplication` |
| X1 `ps -axo command` | 564 lines, 106 of them programs in `/Applications` | exit 255 | `forbidden-exec-sugid` (and `pgrep`: "Cannot get process list") |

**measured**

## 3. TeX

### Setup

The showcase quilt copied to `$F/tex/quilt`; its `drafting/main.tex` uses BibTeX, so a copy `main-biber.tex` uses biblatex with `backend=biber` and the same `refs.bib`. Each run staged `drafting/` into a fresh `$F/tex/run/<name>/stage/drafting` without build products, as `stage_document` does, and ran there with `-outdir` inside the run's folder, in an environment of `PATH` (TeX Live's `bin` first), `HOME` (the decoy), `TMPDIR` inside the run, `LANG`, loom's `openout_any=p` and `shell_escape=p`, and `PAR_GLOBAL_TMPDIR` pointing at `$F/tex/machine/unpacked` (standing for `machine.unpacked()`, unpacked there by the first unfenced run in 13.6 s), or under `tex8` at the run's clone of it. The forms: `latexmk -norc -pdf -interaction=nonstopmode -halt-on-error` on `main.tex` (pdflatex and bibtex) and `main-biber.tex` (pdflatex and biber); `make4ht -m draft -u -c loom-html.cfg -e loom-html.mk4 -d OUT main.tex mathjax` with loom's own configuration, written by `loom.tex.tex4ht.configuration`; and a one-line document that sets `bbm10`, a METAFONT font with no Type 1 version, so `mktexpk` must draw it. make4ht exits 1 both fenced and unfenced on this machine because `pdf2svg` is missing for `figures/quiver.pdf`; its page is made all the same and was compared.

### How the profile was found

| profile | added | outcome |
|---|---|---|
| `tex1` | read the TeX tree, the run, the unpack folder, `/bin`, `/usr/bin`; write the run and the unpack folder | pdflatex failed: `lstat(/usr) failed: /usr: Operation not permitted`, `kpathsea: Can't get directory of program name` |
| `tex2` | ancestors' metadata | bibtex and make4ht passed with identical output; biber failed: "Command Line Tools are not installed" (FENCE-5) |
| `tex3`, `tex4` | the developer folder, `xcrun`'s cache (by its resolved path) | biber passed, identical `.bbl` |
| font | — | failed: `mktexpk` could not write the decoy's `TEXMFVAR`, "Font bbm10 at 600 not found", no PDF |
| `tex5` | read `TEXMFVAR` and `TEXMFHOME`, write `TEXMFVAR/fonts` | all four passed |
| ablation | without `/private/var/select` or `~/.CFUserTextEncoding`: all passed; without `/bin` or `/usr/bin`: the font failed (the `mktex*` scripts) | |
| `tex6` | `tex5` without the two unneeded rules | **all four passed; `.aux`, `.bbl` (both) and `.html` byte-identical to unfenced**; but a run may write biber's whole folder and `xcrun`'s cache (FENCE-12) |
| `tex7` | `xcrun`'s cache read-only (biber passed, same `.bbl`), biber's folder writable only in `thin/` | all four passed, but biber unpacked 202 MB into `TMPDIR` on every run, and failed when its standard output was a file outside the run |
| `tex8` | biber's folder neither read nor written: loom clones it into the run's folder and points `PAR_GLOBAL_TMPDIR` there | **all four passed; `.aux`, `.bbl` (both) and `.html` byte-identical to unfenced; nothing unpacked into `TMPDIR`** |

`tex8`, the profile to build, in full. Its parameters for this machine: `STAGE` the run's folder, `TEXROOT=/usr/local/texlive`, `TEXMFVAR` and `TEXMFHOME` the decoy's (`Library/texlive/2024/texmf-var` and `Library/texmf` under it), `DEVDIR=/Applications/Xcode.app` (the bundle, since `xcrun` reads its `Info.plist` and frameworks), `USERTMP=/private/var/folders/xh/br51g1_j71sdmy2fqdss_blh0000gn/T`.

```scheme
;; A TeX compile, fenced: latexmk with pdflatex, bibtex or biber, and make4ht, in a staged copy of the document's directory.
;; Parameters: STAGE (the run's folder: the staged sources, the output, TMPDIR, make4ht's home, and a copy-on-write clone of biber's unpacked folder),
;; TEXROOT (the TeX installation), TEXMFVAR (TeX's cache for this person), TEXMFHOME (the person's own TeX files),
;; DEVDIR (the developer tools, which TeX Live's universal biber reaches through /usr/bin/lipo), USERTMP (the per-user temporary folder, where xcrun keeps its cache).
(version 1)
(deny default)
(import "system.sb")
(allow process-exec process-fork)
(allow file-read* (subpath (param "STAGE")) (subpath (param "TEXROOT")) (subpath (param "TEXMFVAR")) (subpath (param "TEXMFHOME"))
                  (subpath (param "DEVDIR")) (subpath "/bin") (subpath "/usr/bin")
                  (literal (string-append (param "USERTMP") "/xcrun_db")))
(allow file-read-metadata (path-ancestors (param "STAGE")) (path-ancestors (param "TEXROOT")) (path-ancestors (param "TEXMFVAR"))
                  (path-ancestors (param "TEXMFHOME")) (path-ancestors (param "DEVDIR")) (path-ancestors (param "USERTMP")))
(allow file-write* (subpath (param "STAGE")) (subpath (string-append (param "TEXMFVAR") "/fonts")))
```

Before a run that may call biber, loom clones the machine's unpacked folder into the run's folder (`cp -c -R`, copy-on-write: 0.9–3.2 s for 202 MB in 120 files under loads of 8 to 20; APFS shares the blocks until biber writes, which is read and was not measured) and sets `PAR_GLOBAL_TMPDIR` to the clone; biber rewrites its `thin/` binary and lock files there, and the clone goes when the run's folder does. The first unpack (202 MB, 13.6 s) stays loom's own act outside any compile, as `loom doctor` does it today. The run's standard output and error must be pipes or files inside the run, which loom's `subprocess.PIPE` already is. **measured**

In loom the run's folder is two places, since `compile_document` stages into the system temporary folder and latexmk writes into a run folder beside the output under `.loom`; `STAGE` becomes two parameters. A document that reads another's aux file under `.loom` would need that folder read too (plan 0.32, the move of relloc), which is the "loom's records" of the Formalization row.

### kpathsea without the fence, and the escapes with it

Each attempt is a document of its own (`$F/tex/attack/esc-*.tex`, written by `$F/scripts/gen_esc.py`), since a refused `\openout` ends a nonstop run. Shell escape off is `-no-shell-escape` with `shell_escape=f`, restricted is TeX Live's list with `shell_escape=p`, on is `-shell-escape`. "loom" is `openout_any=p` with `openin_any` unset (TeX Live 2024's `a`); "open" is both `a`.

The fenced column held under `tex6`, `tex7` (both with every mode and both kpathsea settings) and `tex8` (shell escape on and kpathsea open, the widest case, every row but S3 and S5), except where a row says otherwise (`$F/logs/escapes-tex7.log` and the runs under `$F/tex/run/g-*`, `h-*`, `k-*`).

| attempt | unfenced, loom's kpathsea: off / restricted / on | fenced, loom's kpathsea and open, any mode |
|---|---|---|
| R1 `\input` the decoy's `secret.tex` | read into the PDF / same / same | not found |
| R2 `\openin`+`\read` the decoy's `secret.txt` | read / read / read | refused |
| R3 `\openin` `/etc/hosts` | opened / opened / opened | refused |
| R4 `\IfFileExists` `~/.zshenv` | exists / exists / exists | not seen |
| W1 `\openout` an absolute path outside | refused by TeX / same / same (unfenced and open: written) | refused |
| W2 `\openout` `../../../../../outside/…` | refused by TeX (open: written) | refused |
| W3 `\openout` into the decoy's `TEXMFHOME` | refused by TeX (open: written) | refused |
| W4 `\openout` into `TEXMFVAR/fonts` | refused by TeX | refused with loom's kpathsea; **written** with it open (the one place the profile lets a document reach outside its run) |
| W5 `\openout` into the machine's biber unpack folder | refused by TeX | refused with loom's kpathsea; with it open **written** under `tex6`, refused under `tex7` and `tex8` |
| S1 `\write18{cat secret > leak}` | not run / not run / **copied the secret** | not run / not run / `cat` refused, empty file |
| S2 `\write18{echo > outside}` | — / — / **written** | — / — / refused |
| S3 `curl` to `1.1.1.1` and `example.com` | — / — / HTTP 301 and 200 | — / — / curl's LibreSSL could not read `openssl.cnf` (no connection attempted) |
| S6 `nc -z 1.1.1.1 80` | — / — / connected (open, on) | — / — / exit 1, `network-outbound remote:*:80` |
| S7 `dscacheutil` lookup | — / — / resolved (open, on) | — / — / nothing, `network-outbound …/mDNSResponder` |
| S4 `launchctl submit` a job writing outside | — / — / **the job ran and wrote** (removed after) | — / — / `job-creation` refused |
| S5 `kpsewhich` (on the restricted list) | not run / ran / ran | not run / ran / ran (harmless) |
| L1 lualatex, Lua `io.open` the secret | **read** (off and on) | refused |
| L2 Lua `io.open` for writing outside | refused (off), **written** (on) | refused |
| L3 LuaTeX's socket library | absent (off), **connected** (on) | absent / `Operation not permitted` |
| L4 Lua `os.execute` copying the secret | not run (off), **copied** (on) | not run / `cat` refused |

With `openin_any=p` and no fence, R1 to R4 were refused on TeX Live 2024, and lualatex failed before L1 ran (`luaotfload | load : FATAL ERROR`). **measured**

## 4. What it would cost loom

**Building the profile per run.** Two fixed files shipped with loom, one for Lean and one for TeX, and the parameters passed with `-D`. Each parameter is a resolved absolute path loom already knows or can ask once: the quilt's Lean folder and the run's folders; `~/.elan` or `ELAN_HOME`; the TeX root (`kpsewhich -var-value=TEXMFROOT`'s parent, or loom's own TeX under its machine folder), `TEXMFVAR` and `TEXMFHOME` (`kpsewhich -var-value=…`); the developer folder (`xcode-select -p`); the per-user temporary folder (`getconf DARWIN_USER_TEMP_DIR`, resolved). Loom also prepares the run's folder (the staged sources, a clone of `machine.unpacked()` for biber, `TEXMFVAR/fonts` made), sets the environment (a home of the run's own, `TMPDIR` inside the run, `PAR_GLOBAL_TMPDIR` at the clone, `PATH` of resolved folders, the developer folder's `git` first) and starts `/usr/bin/sandbox-exec -f PROFILE -D … -- program …` instead of the program. `subprocess` is unchanged otherwise, and the process group, timeout and `stop_run` stay as they are.

**Machines laid out differently.** Each case changes a parameter, not the profile, provided loom resolves symbolic links before passing paths: Intel Homebrew puts elan's proxies at `/usr/local/bin` and the Cellar at `/usr/local/Cellar` (`ELANBIN=/usr/local`); the official elan installer puts them in `~/.elan/bin` (inside `ELAN`, so `ELANBIN` is not needed); MacTeX's `PATH` entry `/Library/TeX/texbin` is a link to `/usr/local/texlive/<year>/bin/universal-darwin`, so loom must put the resolved folder on `PATH` or allow the link; loom's own TeX lives under `~/Library/Application Support/loom`, a home folder path whose ancestors the profile already lets be looked at but not listed; a machine with only the Command Line Tools has `DEVDIR=/Library/Developer/CommandLineTools`. Calling the toolchain's `lake` directly removes Homebrew and `/private/etc/ssl` from the Lean profile altogether. None of these other layouts was tried.

**What the person sees.** FENCE-11's messages, unless loom reads the refusals itself. The cheap form: after a run that failed, `log show --start <run's start> --predicate 'eventMessage CONTAINS "Sandbox:" AND eventMessage CONTAINS " deny("'`, keep the lines whose process is one of the run's programs, drop the known harmless ones (`/dev/tty`, `~/.CFUserTextEncoding`, Perl's `/Library/Perl/…/AppendToPath`, `/private/var/select/sh` metadata), and show "the fence refused to let TeX read `~/Library/texmf/tex/latex/mine.sty`" beside TeX's own message. A query over the last 30 s took 0.03–0.04 s; the trial waited 1.5 s after each run before reading, and found its refusals there every time. The refusals that are expected and harmless during a passing run are few: `/dev/tty` from latexmk's shells, Perl's `AppendToPath`, and git's `~/.CFUserTextEncoding`.

**An agent's sandbox.** FENCE-9: loom must start every fenced run from its own server process, and a `loom` command run from an agent's shell that wants a run must hand it to the server, or detect that it is sandboxed (Homebrew calls `sandbox_check(getpid(), NULL, 0)`) and say it cannot. Conversely the fence does not stop an agent: it applies only to the processes loom starts.

**Time.** The fence adds nothing that could be measured, beyond the clone of biber's folder. Under loads of 3 to 23 the wall clock followed the load, not the fence, so the comparison is the CPU time (user and system) of each step's whole process tree, unfenced and fenced in alternation (`$F/scripts/cputime`, `$F/logs/cpu-batch.log`; Lean under `lean6`, TeX under `tex7`, biber under `tex8` with its clone):

| step | unfenced CPU, s | fenced CPU, s | unfenced wall, s | fenced wall, s |
|---|---|---|---|---|
| latexmk, pdflatex and bibtex (three pairs) | 4.5, 5.3, 4.4 | 4.5, 4.6, 3.7 | 5.5, 7.3, 4.7 | 5.6, 4.9, 3.7 |
| latexmk, pdflatex and biber (five pairs, the clone not counted) | 7.5, 7.6, 7.6, 8.0, 8.5 | 7.5, 7.6, 7.7, 7.6–8.0, 8.5 | 17.5, 9.9, 10.1, 20.1, 35.0 | 21.1, 19.1, 18.5, 21.6–22.9, 35.3–36.3 |
| make4ht | 2.3, 2.4, 1.6 | 2.6, 2.5, 1.7 | 2.5, 2.7, 1.8 | 3.6, 2.8, 1.7 |
| a no-op `lake build` (traces and git) | 19.9, 20.6, 13.5 | 21.3, 20.0, 12.0 | 15.9, 13.5, 9.7 | 16.9, 14.0, 6.2 |
| `#print axioms` (two pairs) | 13.0, 10.8 | 11.0, 10.8 | 105.1, 67.5 | 74.4, 66.8 |
| `leanchecker` replay (one pair) | 16.4 | 21.7 | 73.0 | 80.1 |

The whole check (rebuild, axioms, replay) took 337 s and 519 s unfenced and 635 s and 303 s fenced, run in alternation at loads of 7 to 15 (`$F/logs/timing-batch.log`), and 284 s fenced under `lean6` at a load of 2 to 5: the spread is the machine's. In the first three biber pairs the fenced run took 3.6, 9.2 and 8.4 s longer on the wall clock with the same CPU; in the last two (one of them with `xcrun`'s cache writable, to test that as the cause) it took the same as unfenced. No refusal was logged and the cause was not found. The first fenced biber timings were void and are not in the table: under `tex7`, and under `tex8` with the clone misplaced, biber failed on its standard output or unpacked a fresh copy into `TMPDIR` (13 s of CPU against 8) (FENCE-12). **measured**

**What it does not cover.** The fence allows reading the whole toolchain, the TeX tree, the developer folder and `/bin` and `/usr/bin`, which hold nothing of the person's; it allows the metadata of every ancestor folder of those places, so a document can learn that `/Users/isaac` exists but not list it; it allows `system.sb`'s Mach services, among them `opendirectoryd`, so a run can learn the person's user name and home path. It does not limit time, memory or disk, which `setrlimit` and the existing timeouts must do: a run that needs Mathlib rebuilt would compile for hours inside the fence (FENCE-8). It does not stop a document writing `TEXMFVAR/fonts` once TeX's own `openout_any` is opened, though what is written there is read as fonts. It runs Apple's private profile `system.sb`, which an update can change.

## 5. Recommendation

**Fence both with `sandbox-exec` for v0.1.** The mechanism held against every attempt made here, costs one extra program in front of the real one, needs nothing installed, signed or approved, and is what Homebrew and Claude Code already rely on. Its risk is Apple's word "deprecated", which so far has meant no new API for fourteen years; loom should notice the day it goes rather than plan around it.

1. **One way to start a fenced run, used by both.** Decision 16's general mechanism: a function that takes a profile name, the parameters and the command, starts `/usr/bin/sandbox-exec -f <profile shipped with loom> -D …` from loom's own process with an environment loom writes whole (a run home, `TMPDIR` inside the run, a `PATH` of resolved folders), keeps today's process group, timeout and `stop_run`, and on a failure reads the run's refusals from the unified log and names them. Paths are passed as parameters, resolved, and never written into profile text.
2. **Lean: the check runs fenced or not at all.** Profile `lean6`; the toolchain found from `lean-toolchain` and called directly, elan never run; `git` from `xcode-select -p`'s folder. Before the fenced steps, without running anything the project carries, loom checks that the toolchain folder and `.lake/packages` exist, and the first fenced step is `lake build --no-build Mathlib` (exit 0 in 10 s when Mathlib is whole; aimed at Mathlib because the check has just removed the project's own build, which `--no-build` of the project's module would also report), so that a run which would compile Mathlib is refused with a sentence instead of starting. If the fence cannot be put up (no `/usr/bin/sandbox-exec`, or `sandbox_apply` refused because loom itself is inside a sandbox), loom runs nothing and says that it could not check the lemma on this machine; the record says "not checked by loom". Decision 16 asks for the fence, so there is no unfenced fallback to offer.
3. **TeX: every program loom starts for a document runs fenced.** Profile `tex8`, for latexmk and what it runs, make4ht and what it runs, and `extractbb`; loom keeps `openout_any=p` and `shell_escape=p` as a second wall. Prepared outside the fence by loom, since none of it reads a document: biber unpacked once into the machine's folder (`loom doctor` does this today) and cloned copy-on-write into each run that may call it, `xcrun --find lipo` run, which should leave `xcrun`'s cache warm (not tried: the cache was present throughout the trial, and without it biber took twice as long), and `TEXMFVAR/fonts` made. If the fence cannot be put up, loom compiles as it does today and the pilot is told SEC-3's limit in one sentence: a document compiled outside the fence can read any file you can read and print it into its PDF.
4. **What to tell the pilots.** "Loom compiles your documents and checks Lean proofs inside a fence: nothing they run can use the network, write outside the build's own folder and TeX's font cache, or read outside the document's folder, TeX or Lean, and Apple's developer tools. A document that reads a file from elsewhere on your Mac by its full path, or a style kept in a folder TeX does not search, fails to compile, and loom names the file it refused." Name the residuals too: a document can learn that a few folders exist (the parents of the places it may read) and the person's user name, and the fence is a facility Apple calls deprecated.
5. **Tests.** The trial's escape documents and the Lean escape module become fixtures: each attempt refused under the fence, and the showcase's compiles identical fenced and unfenced. Whether GitHub's macOS runners allow `sandbox-exec` was not checked.

Not to do: a profile that lets a run write a place holding code an unfenced program later runs (biber's whole cache, `xcrun`'s cache, `TEXMFVAR/luatex-cache`); a fence started from a `loom` command in an agent's shell; and showing a tool's raw message as the reason a fenced run failed.

## 6. Not tested

- TeX Live 2026, and loom's own TeX built from TinyTeX, which is what a pilot gets: its `openin_any` is read to be ignored, and its `biber` was not run fenced or unfenced.
- A Mac without Xcode or the Command Line Tools, Intel, Homebrew under `/usr/local`, elan from the official installer, MacTeX's `/Library/TeX/texbin` on `PATH`.
- Claude Code with its sandbox switched on, and Codex: nesting was measured with `sandbox-exec` layers only.
- loom itself running a fenced compile: no loom code was changed; the runs reproduce `stage_document`, `tex_env` and `_pass` by hand.
- XeLaTeX, `minted` or any package that needs shell escape on (they would fail fenced for the same reason they fail with loom's `shell_escape=p` today), `dvisvgm` with Ghostscript, `pdf2svg`.
- Whether macOS's sandbox matches paths case-insensitively on a case-insensitive volume when loom passes a path in another case.
- A tagged denial: `(with message "…")` on a deny rule produced no log line here, so runs cannot be told apart by tag.
- A real lualatex document under `tex8`: only the escape documents ran under lualatex. A document whose fonts are not yet in luaotfload's database needs to write `TEXMFVAR/luatex-cache`, which `tex8` refuses; here the system-wide database under `/usr/local/texlive/2024/texmf-var` served.
- `xcrun`'s cache missing, as after a reboot or an Xcode update: the profile only reads it, and the slow path without it was tried only under a profile that also allowed Xcode's preferences.
- What made three fenced biber runs 4–9 s slower on the wall clock with the same CPU.
- The trial's harness ran each program through `/usr/bin/env -i` under the fence and wrote standard output to files; loom would use pipes. The harness's own refusals (`/usr/bin/env`, the log file's metadata) are left out of the tables.

## 7. What is installed, and how to remove it

Nothing was installed system-wide and no shell profile was changed. `sudo` was not used. Nothing was written under `~/notes`, `~/quilts`, `~/.config/loom` or `~/Library/Application Support/loom`.

| what | where | size | remove with |
|---|---|---|---|
| the Lake project with Mathlib (7.2 GB), the copies without `.lake`, the TeX runs (51 MB, after removing the 5.6 GB of copies biber unpacked into them), biber's trial unpack folder (202 MB), the decoy home, profiles, scripts and logs | `/private/tmp/claude-501/-Users-isaac-dev-loom-arras/f0ec29b5-fd45-4e3f-ae50-d9f9d632cd2f/scratchpad/fence-trial` | 7.5 GB | `rm -rf` of that folder |
| a line in elan's list of projects, written by `lake update` | `~/.elan/known-projects` (the earlier trial's line is there too) | 250 bytes | harmless; delete the line naming `fence-trial` |
| launchd jobs the unfenced escapes submitted (`fence.trial.s4`, `fence.trial.lean`) | the person's launchd domain | — | already removed with `launchctl remove`; `launchctl list | grep fence.trial` is empty |
| the Lean toolchain, elan and `~/.cache/mathlib` | from the earlier trial, unchanged | 3.0 GB, 5.9 MB, 455 MB | as `raw/lean-trial.md` section 7 says |

`xcrun`'s cache (`xcrun_db` in the per-user temporary folder, 23 MB) is the system's own; `xcrun` rewrote it during the trial, unfenced and under the early profiles that let it, and it needs no removal. No server was started and no port opened. Everything the trial ran is stopped (`pgrep` finds no `lake`, `lean`, `sandbox-exec` or trial script). The scratch folder is the only thing to remove, and nothing else depends on it.
