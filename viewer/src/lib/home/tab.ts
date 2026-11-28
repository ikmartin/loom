// The home page's browser tab, by name. The home names its own tab so and opens each quilt in a tab that keeps it as its opener, so a quilt's Your quilts (`shell/column/YourQuilts.svelte`), a link aimed at this name, brings that tab forward and loads the home there rather than opening a second home. A quilt's tab the home did not open (one a link or `loom serve` opened) cannot reach it, and opens one home tab of this name, which its later clicks reuse.

export const HOME_TAB = 'loom-home';
