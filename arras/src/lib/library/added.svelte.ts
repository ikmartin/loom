// The work the intake added last, which a list of works lights so the person sees where it went without being taken anywhere; and the works a take made without the network added by an identifier loom found, each asking in its row whether to look it up this once.

import { SvelteSet } from 'svelte/reactivity';

export const lastAdded = $state<{ ref: string | null }>({ ref: null });

/** Works whose row asks "look it up this once?", by reference, until the person answers. */
export const asking = new SvelteSet<string>();
