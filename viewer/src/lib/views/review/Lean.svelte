<script lang="ts">
	// Lean as Lean prints it, in a code block: its first word, the declaration's kind, and the declaration's name set apart, as round six sets them.
	let { code }: { code: string } = $props();
	const head = $derived(/^(theorem|lemma|def|abbrev|structure|inductive|instance|axiom|opaque)(\s+)(\S+)/.exec(code));
</script>

<pre class="lean">{#if head}<span class="kw">{head[1]}</span>{head[2]}<span class="nm">{head[3]}</span>{code.slice(head[0].length)}{:else}{code}{/if}</pre>

<style>
	.lean {
		margin: 0;
		padding: 8px 10px;
		border-radius: 6px;
		background: var(--leaf);
		font-family: var(--font-mono, monospace);
		font-size: 12px;
		line-height: 1.55;
		white-space: pre-wrap;
		color: var(--ink);
	}
	.kw {
		color: var(--ink-soft);
	}
	.nm {
		color: var(--link);
	}
</style>
