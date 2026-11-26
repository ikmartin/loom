// Lean on this computer: Settings › Lean (the switch, the install's progress and how it ended, Check again) and Check again where the Web shows a result's Lean. An entry is named for the place it shows, with a comment saying where, on one line.

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
/** Seconds as a person says them: "40 seconds", "3 minutes". */
const took = (s: number) => (s < 90 ? plural(Math.max(1, Math.round(s)), 'second', 'seconds') : plural(Math.round(s / 60), 'minute', 'minutes'));

export const lean = {
	settings: {
		/** The section's name in the Settings panel. */
		section: 'Lean',
		/** Under the section's title: where the switch is kept. */
		where: 'Kept on this computer for this quilt alone, never in the quilt, so a co-author who opens it runs nothing until they turn it on themselves. Only you turn it on or off; an agent cannot.',
		/** The switch's row. */
		name: 'Formalize with Lean',
		/** What the switch does: it says that loom runs Lean, and when. */
		what: "Installs Lean and Mathlib on this computer, about 11 GB and a few minutes the first time, and makes the quilt's Lean project in `lean/`, where an agent writes Lean. From then loom runs Lean itself, with no network and writing only in `lean/`, to check what the agent wrote, and again whenever that Lean or a statement it states changes. Off, loom runs no Lean here; what it installed stays.",
		/** The check's row. */
		check: 'Check the Lean',
		/** What the check does. */
		checkWhat: "Loom rebuilds the project from clean and replays it in Lean's kernel, then records what Lean accepted for each result a declaration states. Your agent asks for this itself; here you can ask for it again.",
		/** When the publisher cannot turn Lean on. */
		cannot: 'The loom serving this quilt cannot turn Lean on. Stop loom serve, run it again, then reload.',
		/** A viewer with no publisher serving it. */
		published: 'Shown as published. Turning Lean on needs loom serving this quilt.'
	},
	/** The line under the switch while it is on and nothing runs. */
	ready: (project: string) => `On. The Lean project is in ${project}/.`,
	/** The same, where the quilt has no project yet: the install has not made one. */
	noProject: 'On, but the quilt has no Lean project yet. Install again to make it.',
	/** Where the fence cannot be put up: loom will not run Lean here, and says why by its code. */
	noFence: {
		absent: 'Loom cannot check Lean on this computer: it has no sandbox loom can run Lean in.',
		nested: 'Loom cannot check Lean from here: the loom serving this quilt runs inside a sandbox of its own, such as an agent’s. Serve the quilt from a terminal of your own.',
		leaks: 'Loom cannot check Lean on this computer: its sandbox lets a run read outside the folders it is given.'
	} as Record<string, string>,
	/** The same for a code with no sentence. */
	noFenceOther: 'Loom cannot check Lean on this computer.',
	/** The install's progress, by the step it is on. */
	installing: (step: string) => `Installing Lean: ${step}…`,
	/** Each step of the install, by its code. */
	installStep: {
		'': 'starting',
		elan: 'installing elan, Lean’s installer',
		project: 'making the Lean project',
		toolchain: 'installing the Lean toolchain',
		mathlib: 'fetching Mathlib, about 1.3 GB the first time'
	} as Record<string, string>,
	/** The install finished. */
	installed: (seconds: number) => (seconds >= 1 ? `Lean is installed. That took ${took(seconds)}.` : 'Lean is installed.'),
	/** The install stopped, at the step it was on. */
	installFailed: (step: string) => (step ? `Installing Lean stopped while ${step}.` : 'Installing Lean stopped.'),
	/** The check's progress, by the step it is on. */
	checking: (step: string) => `Checking the Lean: ${step}…`,
	/** Each step of the check, by its code. */
	checkStep: {
		'': 'starting',
		mathlib: 'making sure Mathlib’s build is whole',
		build: 'building the project from clean',
		probe: 'replaying it in Lean’s kernel'
	} as Record<string, string>,
	/** The check finished: what it recorded. */
	checked: (written: number, unchanged: number) =>
		written || unchanged ? `Checked. ${written ? `${plural(written, 'result', 'results')} recorded anew` : 'Nothing new to record'}${unchanged ? `, ${plural(unchanged, 'result', 'results')} as before` : ''}.` : 'Checked. No declaration states a result yet.',
	/** After it: Lean's errors. */
	errors: (n: number) => `Lean reported ${plural(n, 'error', 'errors')}.`,
	/** After it: markers that name no result of the quilt. */
	unknown: (n: number) => (n === 1 ? 'One declaration is marked for a result the quilt does not have.' : `${n} declarations are marked for results the quilt does not have.`),
	/** The check stopped, at the step it was on. */
	checkFailed: (step: string) => (step ? `The check stopped while ${step}, and recorded nothing.` : 'The check did not run, and recorded nothing.'),
	/** The fold under a failure, holding what loom and Lean said. */
	details: 'What loom said',
	/** The switch's accessible name. */
	switch: 'Formalize with Lean',
	/** The button that runs the install again, after one that stopped or left no project. */
	again: 'Install again',
	/** The button that runs loom's check again, in Settings › Lean and beside a result's Lean in the Web. */
	checkAgain: 'Check again',
	/** Its hover text. */
	checkAgainHover: 'Have loom check the quilt’s Lean again now',
	/** While a press waits for loom's answer. */
	asking: 'Asking loom…'
};
