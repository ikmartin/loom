# The library mock-up, round six

The clickable mock-up of the four views (Docs, Library, Web, Review) that the author settled on 2026-11-21 as the one the viewer is built from: "Round six is indeed settled enough to build the viewer. The important thing to nail is everything on the backend, the frontend can be tweaked later." It is kept here so that what is built can be compared against it. It is not the product, and nothing in it is live: its papers, names and results are invented.

- `index.html` is the prototype. Open it in a browser at 1440 by 900; it makes no network request. The strip at the top, outside the application, moves between screens.
- `NOTES.md` is the designer's notes on this round.
- `marks.md` holds the author's 25 marks on rounds three to five, in his words, with the ruling on each. It is what this round was drawn from.
- `screens/` holds a picture of every screen that changed in this round.

Three things were ruled after the round was drawn, and the build follows the ruling where the picture differs: the list under `Everything` in Review is ordered by who is waiting, the side column staying alphabetical; the formalize panel's "Needed first" is two headed parts, "Stops the request" and "Before it reads formalized"; and an unread or unchecked library result does not stop a request to formalize. The design is `docs/design/library.md`.
