<script lang="ts">
	// Settings › Lean: the switch, the person's alone, kept on this computer for this quilt (`formal-enable`), with the install's progress and how it ended under it; and Check again (`formal-check`) with the check's. Read from `formal-state` (formalize/lean.svelte.ts). A page shown as published, and a loom that serves no `formal-state`, show a line saying so.
	import { lean } from '$lib/formalize/lean.svelte';
	import { fenceLine, jobLines, offersCheck, offersInstall, running, standing } from '$lib/formalize/said';
	import { lean as words } from '$lib/words/lean';
	import { capabilities } from '$lib/write';
	import Row from './Row.svelte';
	import Toggle from './Toggle.svelte';

	let published = $state(false);
	$effect(() => {
		void capabilities().then((caps) => (published = !caps));
		void lean.load();
	});

	const s = $derived(lean.state);
	const job = $derived(s?.job ?? null);
	// the install's lines sit under the switch, the check's under Check again
	const installLines = $derived(job?.kind === 'install' ? jobLines(job) : []);
	const checkLines = $derived(job?.kind === 'check' ? jobLines(job) : []);
</script>

{#snippet failed()}
	{#if job?.state === 'failed' && job.said}
		<details class="said" data-testid="lean-details"><summary>{words.details}</summary><pre>{job.said}</pre></details>
	{/if}
{/snippet}

<div class="card">
	<Row id="lean.on" stack refused={lean.refused}>
		{#if lean.served === false}<p class="line" data-testid="lean-not-served">{published ? words.settings.published : words.settings.cannot}</p>
		{:else if s}
			<div class="switch">
				<!-- drawn again at each answer to a press: a flip loom refused goes back to what the state says -->
				{#key lean.answers}<Toggle checked={s.on} set={(on) => void lean.enable(on)} label={words.switch} test="lean-switch" disabled={lean.busy} />{/key}
				{#if offersInstall(s)}<button class="btn" disabled={lean.busy} onclick={() => void lean.enable(true)} data-testid="lean-install">{words.again}</button>{/if}
			</div>
			<div class="lines" aria-live="polite" data-testid="lean-install-lines">
				{#each installLines as line, i (i)}<p class="line" class:going={running(s)}>{line}</p>{/each}
				{#if job?.kind === 'install'}{@render failed()}{/if}
				{#if standing(s)}<p class="line" data-testid="lean-standing">{standing(s)}</p>{/if}
				{#if fenceLine(s)}<p class="line warn" data-testid="lean-fence">{fenceLine(s)}</p>{/if}
			</div>
		{/if}
	</Row>
	{#if s?.on}
		<Row id="lean.check" stack>
			<div class="switch">
				<button class="btn" disabled={lean.busy || !offersCheck(s)} title={words.checkAgainHover} onclick={() => void lean.check()} data-testid="lean-check">{lean.busy ? words.asking : words.checkAgain}</button>
			</div>
			<div class="lines" aria-live="polite" data-testid="lean-check-lines">
				{#each checkLines as line, i (i)}<p class="line" class:going={running(s)}>{line}</p>{/each}
				{#if job?.kind === 'check'}{@render failed()}{/if}
			</div>
		</Row>
	{/if}
</div>

<style>
	.switch {
		display: flex;
		align-items: center;
		gap: 12px;
		margin-top: 10px;
	}
	.lines {
		margin-top: 6px;
	}
	.line {
		margin: 6px 0 0;
		font-size: 13px;
		color: var(--ink-soft);
	}
	.line.going {
		color: var(--ink);
	}
	.line.warn {
		color: var(--state-conflicted);
	}
	.said {
		margin-top: 6px;
		font-size: 12.5px;
		color: var(--ink-faint);
	}
	.said summary {
		cursor: pointer;
	}
	.said pre {
		margin: 6px 0 0;
		padding: 8px 10px;
		max-height: 220px;
		overflow: auto;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		font-family: var(--mono);
		font-size: 11.5px;
		background: var(--wash, transparent);
		border: 1px solid var(--rule);
		border-radius: 6px;
	}
</style>
